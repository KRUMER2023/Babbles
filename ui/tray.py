"""
ui/tray.py
──────────
System-tray icon for Babbles using pystray + Pillow.

The tray icon is drawn programmatically (microphone shape) so no image
file is required.  Right-click menu items:
  • Settings  — opens the settings window
  • ─────────
  • Quit      — exits the application

The tray runs on its own daemon thread; all Tk interactions are posted
via root.after() to stay thread-safe.

Changelog
─────────
v0.1.0 – Initial implementation (pystray, programmatic mic icon, menu).
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from typing import Callable

from PIL import Image, ImageDraw
import pystray


# ── Icon generator ────────────────────────────────────────────────────────────

def _make_icon(size: int = 64) -> Image.Image:
    """Draw a simple microphone icon as a PIL Image."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size
    # Body of mic (rounded rectangle)
    bx0, by0, bx1, by1 = s*0.35, s*0.10, s*0.65, s*0.62
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=s*0.14, fill="#f85149")

    # Arc (stand bow)
    draw.arc([s*0.20, s*0.38, s*0.80, s*0.78], start=0, end=180, fill="#c9d1d9", width=max(2, s//14))

    # Stand pole
    cx = s * 0.50
    draw.line([(cx, s*0.78), (cx, s*0.90)], fill="#c9d1d9", width=max(2, s//14))

    # Stand base
    draw.line([(s*0.30, s*0.90), (s*0.70, s*0.90)], fill="#c9d1d9", width=max(2, s//14))

    return img


def _load_icon() -> Image.Image:
    """Load the transparent Babbles logo icon from the project root."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    icon_path = os.path.join(project_root, "babbles_logo.ico")
    return Image.open(icon_path)


# ── TrayApp ───────────────────────────────────────────────────────────────────

class TrayApp:
    """
    Manages the system-tray icon lifecycle.

    Parameters
    ----------
    root:            Tk root window (for posting settings-open callbacks).
    on_open_settings: Called when the user clicks "Settings".
    on_quit:          Called when the user clicks "Quit".
    """

    def __init__(
        self,
        root:             tk.Tk,
        on_open_settings: Callable | None = None,
        on_quit:          Callable | None = None,
        is_listening_fn:  Callable[[], bool] | None = None,
        on_toggle_listening: Callable[[], None] | None = None,
    ) -> None:
        self._root                = root
        self._on_open_settings    = on_open_settings
        self._on_quit             = on_quit
        self._is_listening_fn     = is_listening_fn
        self._on_toggle_listening = on_toggle_listening
        self._icon: pystray.Icon | None = None

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Build and start the tray icon.  Blocks until icon.stop() is called."""
        def get_toggle_text(item) -> str:
            if self._is_listening_fn and self._is_listening_fn():
                return "⏹  Stop Listening"
            return "🎙  Start Dictation"

        menu = pystray.Menu(
            pystray.MenuItem(get_toggle_text, self._toggle_clicked),
            pystray.MenuItem("⚙  Settings", self._settings_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕  Quit Babbles", self._quit_clicked),
        )
        self._icon = pystray.Icon(
            name="Babbles",
            # icon=_make_icon(),
            icon=_load_icon(),
            title="Babbles — Speech to Text",
            menu=menu,
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def set_tooltip(self, text: str) -> None:
        """Update the hover tooltip (e.g. 'Babbles — Recording…')."""
        if self._icon:
            self._icon.title = text

    # ------------------------------------------------------------------ #

    def _toggle_clicked(self, icon, item) -> None:
        if self._on_toggle_listening:
            self._root.after(0, self._on_toggle_listening)

    def _settings_clicked(self, icon, item) -> None:
        if self._on_open_settings:
            self._root.after(0, self._on_open_settings)

    def _quit_clicked(self, icon, item) -> None:
        self.stop()
        if self._on_quit:
            self._root.after(0, self._on_quit)
        else:
            self._root.after(0, self._root.quit)
