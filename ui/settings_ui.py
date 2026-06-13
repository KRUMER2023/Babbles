"""
ui/settings_ui.py
─────────────────
Settings window built with CustomTkinter.

Opens as a Toplevel attached to the Tk root.  Changes are written back
to config.json via the save callback supplied by main.py.

Options exposed
───────────────
• Whisper model size  (tiny / base / small / medium)
• Device              (cuda / cpu)
• Language            (en / auto / …)
• Clipboard restore delay (ms)

Changelog
─────────
v0.1.0 – Initial implementation (CustomTkinter settings window, config save).
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

_MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]
_DEVICES     = ["cuda", "cpu"]
_LANGUAGES   = ["en", "auto", "fr", "de", "es", "pt", "ja", "zh"]


class SettingsWindow:
    """
    Modal-ish settings panel.

    Parameters
    ----------
    root:        Tk root window.
    config:      Current configuration dict (will be mutated on save).
    on_save:     Called with the updated config dict when user clicks Save.
    """

    def __init__(
        self,
        root:    tk.Tk,
        config:  dict,
        on_save: Callable[[dict], None] | None = None,
    ) -> None:
        self._root    = root
        self._config  = config
        self._on_save = on_save
        self._win: ctk.CTkToplevel | None = None

    # ------------------------------------------------------------------ #

    def open(self) -> None:
        """Open (or focus) the settings window."""
        if self._win and self._win.winfo_exists():
            self._win.focus_force()
            return
        self._build()

    def _get_input_devices(self) -> list[str]:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = ["Default"]
            for i, d in enumerate(devices):
                if d.get("max_input_channels", 0) > 0:
                    input_devices.append(f"{i}: {d['name']}")
            return input_devices
        except Exception:
            return ["Default"]

    def _build(self) -> None:
        win = ctk.CTkToplevel(self._root)
        win.title("Babbles — Settings")
        win.geometry("420x420")
        win.resizable(False, False)
        win.grab_set()          # modal behaviour
        self._win = win

        pad = {"padx": 20, "pady": 8}

        # ── Title ──────────────────────────────────────────────────────
        ctk.CTkLabel(win, text="⚙  Settings",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))

        frame = ctk.CTkFrame(win)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Microphone
        devices_list = self._get_input_devices()
        current_device = self._config.setdefault("audio", {}).get("device")
        default_val = "Default"
        if current_device is not None:
            for dev in devices_list:
                if dev.startswith(f"{current_device}:"):
                    default_val = dev
                    break

        self._var_mic = tk.StringVar(value=default_val)
        self._row(frame, 0, "Microphone", ctk.CTkOptionMenu(
            frame, variable=self._var_mic, values=devices_list, width=160))

        # Model size
        self._var_model = tk.StringVar(value=self._config["model"]["size"])
        self._row(frame, 1, "Whisper model", ctk.CTkOptionMenu(
            frame, variable=self._var_model, values=_MODEL_SIZES, width=160))

        # Device
        self._var_device = tk.StringVar(value=self._config["model"]["device"])
        self._row(frame, 2, "Device", ctk.CTkOptionMenu(
            frame, variable=self._var_device, values=_DEVICES, width=160))

        # Language
        self._var_lang = tk.StringVar(value=self._config["model"].get("language", "en"))
        self._row(frame, 3, "Language", ctk.CTkOptionMenu(
            frame, variable=self._var_lang, values=_LANGUAGES, width=160))

        # Clipboard restore delay
        self._var_delay = tk.StringVar(
            value=str(self._config["output"]["clipboard_restore_delay_ms"]))
        entry = ctk.CTkEntry(frame, textvariable=self._var_delay, width=80)
        self._row(frame, 4, "Clipboard restore (ms)", entry)

        # Show Terminal
        self._var_show_terminal = tk.BooleanVar(value=self._config.setdefault("ui", {}).get("show_terminal", False))
        switch = ctk.CTkSwitch(frame, text="", variable=self._var_show_terminal, width=40)
        self._row(frame, 5, "Show Terminal", switch)

        # ── Buttons ────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(4, 16))

        ctk.CTkButton(btn_frame, text="Cancel", fg_color="#30363d",
                      command=win.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Save", command=self._save).pack(side="right")

    @staticmethod
    def _row(parent: ctk.CTkFrame, row: int, label: str, widget) -> None:
        ctk.CTkLabel(parent, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=6)
        widget.grid(row=row, column=1, sticky="e", padx=12, pady=6)

    def _save(self) -> None:
        """Write widget values back to the config dict and call on_save."""
        selected_mic = self._var_mic.get()
        if selected_mic == "Default":
            self._config.setdefault("audio", {})["device"] = None
        else:
            try:
                device_idx = int(selected_mic.split(":")[0])
                self._config.setdefault("audio", {})["device"] = device_idx
            except ValueError:
                self._config.setdefault("audio", {})["device"] = None

        self._config["model"]["size"]     = self._var_model.get()
        self._config["model"]["device"]   = self._var_device.get()
        self._config["model"]["language"] = (
            None if self._var_lang.get() == "auto" else self._var_lang.get()
        )
        self._config.setdefault("ui", {})["show_terminal"] = self._var_show_terminal.get()
        
        try:
            delay = int(self._var_delay.get())
            self._config["output"]["clipboard_restore_delay_ms"] = delay
        except ValueError:
            pass

        if self._on_save:
            self._on_save(self._config)

        if self._win:
            self._win.destroy()
