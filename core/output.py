"""
core/output.py
──────────────
Injects transcribed text into the currently focused window via the clipboard.

Strategy (lowest latency, highest compatibility)
────────────────────────────────────────────────
1. Save the user's current clipboard contents.
2. Set the clipboard to the transcribed text.
3. Simulate Ctrl+V to paste.
4. Restore the original clipboard after a short delay.

This avoids pyautogui.typewrite() which is extremely slow for sentences
and has encoding issues with non-ASCII characters.

Changelog
─────────
v0.1.0 – Initial implementation (pyperclip + keyboard, clipboard save/restore).
"""

from __future__ import annotations

import logging
import threading
import time

import keyboard
import pyperclip

logger = logging.getLogger(__name__)

_PASTE_SETTLE_MS: float = 60     # ms to wait after copy before sending Ctrl+V
_DEFAULT_RESTORE_DELAY_MS: float = 250  # ms before restoring old clipboard


class OutputHandler:
    """
    Pastes text into the active window using the clipboard.

    Parameters
    ----------
    restore_delay_ms: How long (ms) to wait before restoring the user's
                      original clipboard content.  Must be long enough for
                      the target application to register the paste.
    """

    def __init__(self, restore_delay_ms: float = _DEFAULT_RESTORE_DELAY_MS) -> None:
        self.restore_delay_ms = restore_delay_ms

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def paste(self, text: str) -> None:
        """
        Paste *text* into the currently focused window.

        Steps
        -----
        1. Read current clipboard → save as ``original``.
        2. Write *text* to clipboard.
        3. Send Ctrl+V.
        4. After ``restore_delay_ms``, restore ``original`` on a daemon thread.
        """
        if not text:
            logger.debug("Empty text — nothing to paste.")
            return

        # 1. Save original clipboard
        try:
            original = pyperclip.paste()
        except Exception:
            original = ""

        # 2. Write new text
        try:
            pyperclip.copy(text)
        except Exception as exc:
            logger.error("Failed to write to clipboard: %s", exc)
            return

        # 3. Short settle time so the OS registers the clipboard change
        time.sleep(_PASTE_SETTLE_MS / 1000)

        # 4. Simulate paste
        keyboard.press_and_release("ctrl+v")
        logger.info("📋 Pasted %d chars.", len(text))

        # 5. Restore original clipboard asynchronously
        threading.Thread(
            target=self._restore_clipboard,
            args=(original,),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _restore_clipboard(self, original: str) -> None:
        time.sleep(self.restore_delay_ms / 1000)
        try:
            pyperclip.copy(original)
            logger.debug("Clipboard restored.")
        except Exception as exc:
            logger.debug("Could not restore clipboard: %s", exc)
