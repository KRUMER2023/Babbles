"""
core/hotkey.py
──────────────
Global Ctrl+Space hotkey listener using the `keyboard` library.

The listener runs via keyboard's internal hook (non-blocking) and fires
thread-safe callbacks when the combo is pressed or released.

NOTE: On Windows the `keyboard` library requires the script to run with
Administrator privileges (or be packaged as an elevated executable).

Changelog
─────────
v0.1.0 – Initial implementation (keyboard hook, press/release state machine).
"""

import logging
import threading
from typing import Callable

import keyboard

logger = logging.getLogger(__name__)


class HotkeyListener:
    """
    Detects global Ctrl+Space (hold-to-speak) and Ctrl+Alt+Space (toggle) patterns.

    * ``on_start`` – called once when the combo is first pressed.
    * ``on_stop``  – called once when the combo is released/toggled off.

    Both callbacks are executed on a fresh daemon thread so they never
    block the keyboard event loop.
    """

    def __init__(self, hotkey: str = "ctrl+space", toggle_hotkey: str = "ctrl+alt+space") -> None:
        self.hotkey        = hotkey
        self.toggle_hotkey = toggle_hotkey
        self._pressed      = False
        self._recording_mode: str | None = None  # None, "hold", or "toggle"
        self._on_start: Callable | None = None
        self._on_stop:  Callable | None = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def set_callbacks(
        self,
        on_start: Callable,
        on_stop:  Callable,
    ) -> None:
        self._on_start = on_start
        self._on_stop  = on_stop

    def start(self) -> None:
        """Attach the global keyboard hook.  Call once at startup."""
        keyboard.hook(self._on_key_event)
        logger.info(
            "⌨  Hotkey listener active — hold [%s] or press [%s] to dictate.",
            self.hotkey, self.toggle_hotkey
        )

    def stop(self) -> None:
        """Detach all keyboard hooks."""
        keyboard.unhook_all()
        logger.info("⌨  Hotkey listener stopped.")

    def reset_state(self) -> None:
        """Reset internal recording state (used when stopped via tray/UI)."""
        self._recording_mode = None
        self._pressed = False
        logger.debug("Hotkey state reset.")

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _on_key_event(self, event: keyboard.KeyboardEvent) -> None:
        """Raw keyboard event handler — detects hotkeys for hold and toggle modes."""
        if event.name != "space":
            return

        ctrl_held = keyboard.is_pressed("ctrl")
        alt_held  = keyboard.is_pressed("alt")

        if event.event_type == keyboard.KEY_DOWN:
            if ctrl_held and alt_held:
                # ── Ctrl+Alt+Space (Toggle Mode) ─────────────────────────────
                if self._recording_mode == "toggle":
                    self._recording_mode = None
                    self._pressed = False
                    logger.debug("Toggle hotkey: stop triggered.")
                    if self._on_stop:
                        threading.Thread(target=self._on_stop, daemon=True).start()
                elif self._recording_mode is None:
                    self._recording_mode = "toggle"
                    self._pressed = True
                    logger.debug("Toggle hotkey: start triggered.")
                    if self._on_start:
                        threading.Thread(target=self._on_start, daemon=True).start()
            
            elif ctrl_held and not alt_held:
                # ── Ctrl+Space (Hold Mode) ───────────────────────────────────
                if self._recording_mode is None:
                    self._recording_mode = "hold"
                    self._pressed = True
                    logger.debug("Hold hotkey: start triggered.")
                    if self._on_start:
                        threading.Thread(target=self._on_start, daemon=True).start()

        elif event.event_type == keyboard.KEY_UP:
            if self._recording_mode == "hold":
                self._recording_mode = None
                self._pressed = False
                logger.debug("Hold hotkey: stop triggered.")
                if self._on_stop:
                    threading.Thread(target=self._on_stop, daemon=True).start()
