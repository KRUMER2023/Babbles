"""
main.py
───────
Babbles entry point.

Boot sequence
─────────────
1. Load config.json.
2. Configure logging.
3. Pre-load the Whisper model on a background thread (so the first press
   has zero model-load latency).
4. Build the hidden Tk root + overlay.
5. Start the system-tray icon on a daemon thread.
6. Attach hotkey callbacks.
7. Hand control to the Tk main loop.

Thread map
──────────
  Main thread    — Tk event loop (overlay, settings window)
  Daemon thread  — pystray tray icon
  Daemon thread  — keyboard hook (fires OS callbacks)
  Daemon thread  — model pre-load
  Daemon thread  — audio → transcribe → paste pipeline (per keypress)

Run with Administrator privileges on Windows so `keyboard` can hook
global events.

Changelog
─────────
v0.1.0 – Initial implementation (full pipeline integration).
v0.1.1 – Fix: set TCL_LIBRARY/TK_LIBRARY before tkinter import (Admin env issue).
"""

from __future__ import annotations  # must be the first statement after the docstring

# ── Tcl/Tk path fix (must happen BEFORE tkinter is imported) ─────────────────
# When Python is run as Administrator on Windows, user-level environment
# variables (TCL_LIBRARY, TK_LIBRARY) are stripped, causing init.tcl lookup
# to fail.  We auto-detect the correct paths from sys.executable and set them
# explicitly so tkinter initialises correctly regardless of privilege level.
import os
import sys as _sys


def _fix_tcl_tk() -> None:
    """
    Set TCL_LIBRARY and TK_LIBRARY if they are missing.

    When Python is launched as Administrator on Windows, user-level env vars
    (including TCL_LIBRARY / TK_LIBRARY) are not inherited, so tkinter cannot
    find init.tcl.  We read the venv pyvenv.cfg 'home' key to get the real
    Python base directory and set the paths explicitly.
    """
    if getattr(_sys, "frozen", False):
        return  # PyInstaller bundles and configures Tcl/Tk automatically

    if "TCL_LIBRARY" in os.environ and "TK_LIBRARY" in os.environ:
        return  # already set — nothing to do

    exe     = _sys.executable
    scripts = os.path.dirname(exe)       # .venv/Scripts
    venv    = os.path.dirname(scripts)   # .venv
    cfg     = os.path.join(venv, "pyvenv.cfg")

    base_python = None
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                key, _, val = line.partition("=")
                key = key.strip().lower().replace("-", "_")
                if key == "home":
                    base_python = val.strip()
                    break

    if not base_python:
        base_python = scripts   # fall back to the Scripts dir

    tcl_dir = os.path.join(base_python, "tcl")
    if not os.path.isdir(tcl_dir):
        return  # can't help — user may need to repair their Python install

    # sorted(reverse=True) ensures tcl8.6 is processed before bare tcl8
    for sub in sorted(os.listdir(tcl_dir), reverse=True):
        full = os.path.join(tcl_dir, sub)
        if not os.path.isdir(full):
            continue
        if sub.startswith("tcl8") and os.path.isfile(os.path.join(full, "init.tcl")):
            os.environ.setdefault("TCL_LIBRARY", full)
        if sub.startswith("tk8") and os.path.isfile(os.path.join(full, "tk.tcl")):
            os.environ.setdefault("TK_LIBRARY", full)


_fix_tcl_tk()  # must be called before `import tkinter`

import ctypes
import json
import logging
import logging.handlers
import threading
import tkinter as tk  # safe to import after _fix_tcl_tk()
from tkinter import messagebox
from pathlib import Path

import numpy as np

from core.audio       import AudioRecorder
from core.hotkey      import HotkeyListener
from core.output      import OutputHandler
from core.transcriber import Transcriber
from ui.overlay       import ListeningOverlay
from ui.settings_ui   import SettingsWindow
from ui.tray          import TrayApp

# ── Paths ────────────────────────────────────────────────────────────────────
if getattr(_sys, "frozen", False):
    # Running inside a PyInstaller bundle
    APP_DIR = Path(_sys.executable).parent
    BUNDLE_DIR = Path(_sys._MEIPASS)
else:
    # Running in developer environment
    APP_DIR = Path(__file__).parent.resolve()
    BUNDLE_DIR = Path(__file__).parent.resolve()

CONFIG_FILE = APP_DIR / "config.json"

# ── Default Configuration (Self-Healing) ──────────────────────────────────────
DEFAULT_CONFIG = {
    "model": {
        "size": "small",
        "device": "cuda",
        "compute_type": "float16",
        "cpu_fallback_compute_type": "int8",
        "language": "en",
        "beam_size": 5,
        "vad_filter": True
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "device": None
    },
    "hotkey": "ctrl+space",
    "toggle_hotkey": "ctrl+alt+space",
    "output": {
        "clipboard_restore_delay_ms": 250
    },
    "ui": {
        "overlay_position": "bottom_center",
        "overlay_margin_bottom_px": 40,
        "show_terminal": False
    },
    "logging": {
        "level": "INFO",
        "file": "babbles.log"
    }
}

# ── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            print(f"Created default config.json at {CONFIG_FILE}")
        except Exception as exc:
            print(f"Warning: Could not create default config.json: {exc}")
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            for section, val in loaded.items():
                if isinstance(val, dict) and section in merged:
                    merged[section].update(val)
                else:
                    merged[section] = val
            return merged
    except Exception as exc:
        print(f"Warning: Failed to load config.json, using defaults. Error: {exc}")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logging.getLogger(__name__).info("Config saved.")
    except Exception as exc:
        logging.getLogger(__name__).error("Failed to save config: %s", exc)


# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(config: dict) -> None:
    level = getattr(logging, config["logging"]["level"].upper(), logging.INFO)
    log_file = APP_DIR / config.get("logging", {}).get("file", "babbles.log")
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            log_file, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
        ),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=handlers,
    )


# ── Application ──────────────────────────────────────────────────────────────

class BabblesApp:
    """Wires all components together and owns the main event loop."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.log    = logging.getLogger(self.__class__.__name__)

        # Core components
        self.recorder    = AudioRecorder(
            sample_rate=config["audio"]["sample_rate"],
            device=config["audio"].get("device")
        )
        self.transcriber = Transcriber(
            model_size   = config["model"]["size"],
            device       = config["model"]["device"],
            compute_type = config["model"]["compute_type"],
            language     = config["model"].get("language") or None,
            beam_size    = config["model"]["beam_size"],
            vad_filter   = config["model"]["vad_filter"],
            download_root= str(APP_DIR / "models"),
        )
        self.output = OutputHandler(
            restore_delay_ms=config["output"]["clipboard_restore_delay_ms"]
        )

        # Tk root (invisible — just event loop + parent for Toplevels)
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Babbles")

        # UI components
        self.overlay  = ListeningOverlay(self.root)
        self.settings = SettingsWindow(self.root, self.config, on_save=self._on_settings_save)
        self.tray     = TrayApp(
            self.root,
            on_open_settings=self.settings.open,
            on_quit=self._on_quit,
            is_listening_fn=self._is_recording,
            on_toggle_listening=self._toggle_listening,
        )

        # Hotkey listener
        self.hotkey = HotkeyListener(
            hotkey=config["hotkey"],
            toggle_hotkey=config.get("toggle_hotkey", "ctrl+alt+space")
        )
        self.hotkey.set_callbacks(
            on_start=self._on_record_start,
            on_stop =self._on_record_stop,
        )

        # Apply initial terminal visibility
        self._apply_terminal_visibility()

    # ------------------------------------------------------------------ #
    #  Startup                                                             #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Start all services and enter the Tk main loop."""
        # 1. Load model in background so UI is ready immediately
        threading.Thread(target=self._load_model, daemon=True, name="ModelLoader").start()

        # 2. Tray icon on its own daemon thread
        threading.Thread(target=self.tray.run, daemon=True, name="TrayIcon").start()

        # 3. Keyboard hook (non-blocking)
        self.hotkey.start()

        self.log.info("Babbles running.  Hold [%s] or press [%s] to transcribe.",
                      self.config["hotkey"], self.config.get("toggle_hotkey", "ctrl+alt+space"))

        # 4. Tk main loop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

    def _load_model(self) -> None:
        try:
            self.transcriber.load()
        except Exception as exc:
            self.log.error("Failed to load model: %s", exc, exc_info=True)
            self.root.after(0, lambda e=exc: messagebox.showerror(
                "Babbles — Model Load Error",
                f"Failed to load the Whisper model ({self.config['model']['size']}).\n\n"
                f"Error: {e}\n\n"
                "Please verify your config.json settings or internet connection."
            ))

    # ------------------------------------------------------------------ #
    #  Hotkey callbacks (run on daemon threads)                            #
    # ------------------------------------------------------------------ #

    def _on_record_start(self) -> None:
        if self.recorder.is_recording:
            return
        self.recorder.start()
        self.overlay.show_listening()
        self.tray.set_tooltip("Babbles — 🎙 Recording…")

    def _on_record_stop(self) -> None:
        if not self.recorder.is_recording:
            return
        # Sync hotkey listener state (handles cases like tray click stops)
        self.hotkey.reset_state()

        audio: np.ndarray = self.recorder.stop()
        self.overlay.show_transcribing()
        self.tray.set_tooltip("Babbles — ⟳ Transcribing…")

        try:
            if not self.transcriber.is_ready:
                self.log.warning("Model not ready yet — skipping transcription.")
                return
            text = self.transcriber.transcribe(audio)
            if text:
                self.output.paste(text)
        except Exception as exc:
            self.log.error("Transcription error: %s", exc, exc_info=True)
        finally:
            self.overlay.hide()
            self.tray.set_tooltip("Babbles — Speech to Text")

    # ------------------------------------------------------------------ #
    #  Tray / UI Action callbacks                                          #
    # ------------------------------------------------------------------ #

    def _is_recording(self) -> bool:
        return self.recorder.is_recording

    def _toggle_listening(self) -> None:
        if self._is_recording():
            self._on_record_stop()
        else:
            self._on_record_start()

    # ------------------------------------------------------------------ #
    #  Misc callbacks                                                      #
    # ------------------------------------------------------------------ #

    def _apply_terminal_visibility(self) -> None:
        """Hide or show the console window based on config."""
        if _sys.platform == "win32":
            show = self.config.get("ui", {}).get("show_terminal", False)
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 5 if show else 0)

    def _on_settings_save(self, new_config: dict) -> None:
        self.config = new_config
        save_config(new_config)
        # Update output handler immediately (no restart needed for simple settings)
        self.output.restore_delay_ms = new_config["output"]["clipboard_restore_delay_ms"]
        # Update active audio recorder device index immediately
        self.recorder.device = new_config.get("audio", {}).get("device")
        # Apply terminal visibility change immediately
        self._apply_terminal_visibility()
        
        self.log.info("Settings updated.  Model changes take effect on next launch.")

    def _on_quit(self) -> None:
        self.log.info("Quitting Babbles.")
        self.hotkey.stop()
        self.root.quit()
        # Restore terminal visibility before exiting so the batch script pause is visible
        if _sys.platform == "win32":
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 5)


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    try:
        config = load_config()
        setup_logging(config)
        app = BabblesApp(config)
        app.run()
    except Exception as exc:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Babbles — Fatal Error",
                f"Babbles encountered a fatal error during startup:\n\n{exc}\n\n"
                "The application will now exit."
            )
            root.destroy()
        except Exception as msgbox_exc:
            print(f"Fatal error message box could not be shown: {msgbox_exc}")
        
        print(f"FATAL STARTUP ERROR: {exc}")
        logging.critical("Fatal startup error", exc_info=True)
        _sys.exit(1)


if __name__ == "__main__":
    main()
