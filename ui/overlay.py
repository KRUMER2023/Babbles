"""
ui/overlay.py
─────────────
Animated floating overlay displayed while the user is holding Ctrl+Space.

Design
──────
* No title-bar, always-on-top, semi-transparent pill at the bottom centre
  of the screen.
* Two states:
    STATE_LISTENING    – animated waveform bars + "● Listening…"
    STATE_TRANSCRIBING – pulsing dots       + "⟳ Transcribing…"
* Built entirely with tkinter (stdlib — no extra dependency).
* All UI mutations are posted via root.after() so they are safe to call
  from any thread.

Changelog
─────────
v0.1.0 – Initial implementation (tkinter overlay, waveform + transcribing states).
"""

from __future__ import annotations

import math
import tkinter as tk
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # only for type hints

# ── Constants ──────────────────────────────────────────────────────────────────
W, H          = 340, 72          # Overlay window size (px)
MARGIN_BOTTOM = 44               # Pixels from screen bottom edge
FPS           = 20               # Animation frames per second

# Colour palette
COL_BG        = "#0d1117"        # Near-black background
COL_BORDER    = "#30363d"        # Subtle border
COL_TEXT      = "#c9d1d9"        # GitHub-flavoured off-white
COL_DOT_REC   = "#f85149"        # Recording red dot
COL_BAR_LOW   = "#58a6ff"        # Bar colour (quiet)
COL_BAR_HIGH  = "#f85149"        # Bar colour (loud / peak)
COL_PULSE     = "#3fb950"        # Transcribing green

NUM_BARS      = 14
BAR_W         = 8
BAR_GAP       = 5
BAR_MAX_H     = 26
BAR_MIN_H     = 3
BAR_BASE_Y    = 60               # Y baseline for bars inside canvas


class OverlayState(Enum):
    HIDDEN        = auto()
    LISTENING     = auto()
    TRANSCRIBING  = auto()


class ListeningOverlay:
    """
    Controls a compact animated overlay window.

    Must be constructed on the same thread as the tkinter ``root``.
    All public methods (``show_listening``, ``show_transcribing``, ``hide``)
    are thread-safe — they schedule work on the Tk event loop.

    Parameters
    ----------
    root: The application's (possibly withdrawn) Tk root window.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root   = root
        self._win:    tk.Toplevel | None = None
        self._canvas: tk.Canvas   | None = None
        self._state   = OverlayState.HIDDEN
        self._phase   = 0.0           # animation phase accumulator
        self._after_id: str | None = None

    # ------------------------------------------------------------------ #
    #  Public API (thread-safe)                                            #
    # ------------------------------------------------------------------ #

    def show_listening(self) -> None:
        """Display the overlay in LISTENING state."""
        self._root.after(0, self._set_state, OverlayState.LISTENING)

    def show_transcribing(self) -> None:
        """Switch overlay to TRANSCRIBING state."""
        self._root.after(0, self._set_state, OverlayState.TRANSCRIBING)

    def hide(self) -> None:
        """Hide the overlay."""
        self._root.after(0, self._set_state, OverlayState.HIDDEN)

    # ------------------------------------------------------------------ #
    #  Internal — must only be called from Tk thread                      #
    # ------------------------------------------------------------------ #

    def _set_state(self, new_state: OverlayState) -> None:
        if new_state == self._state:
            return
        self._state = new_state
        if new_state == OverlayState.HIDDEN:
            self._destroy_window()
        else:
            if self._win is None:
                self._create_window()
            self._start_animation()

    # ── Window management ──────────────────────────────────────────────

    def _create_window(self) -> None:
        self._win = tk.Toplevel(self._root)
        win = self._win

        # Borderless, always-on-top
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.93)

        # Position: bottom centre
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x  = (sw - W) // 2
        y  = sh - H - MARGIN_BOTTOM
        win.geometry(f"{W}x{H}+{x}+{y}")
        win.configure(bg=COL_BG)

        self._canvas = tk.Canvas(
            win, width=W, height=H,
            bg=COL_BG, highlightthickness=0,
        )
        self._canvas.pack()

        # Prevent the overlay from stealing keyboard focus
        win.wm_attributes("-disabled", False)
        win.focus_set()   # don't keep focus; hotkey target should keep it

    def _destroy_window(self) -> None:
        if self._after_id:
            self._root.after_cancel(self._after_id)
            self._after_id = None
        if self._win:
            self._win.destroy()
            self._win    = None
            self._canvas = None

    # ── Animation loop ─────────────────────────────────────────────────

    def _start_animation(self) -> None:
        if self._after_id:
            self._root.after_cancel(self._after_id)
        self._phase = 0.0
        self._animate()

    def _animate(self) -> None:
        if self._state == OverlayState.HIDDEN or self._canvas is None:
            return

        c = self._canvas
        c.delete("all")

        # ── Pill background ──────────────────────────────────────────────
        r = 18
        c.create_arc( 2,  2, 2+2*r, H-2, start= 90, extent=180, fill=COL_BG, outline=COL_BORDER, width=1)
        c.create_arc(W-2-2*r, 2, W-2, H-2, start=270, extent=180, fill=COL_BG, outline=COL_BORDER, width=1)
        c.create_rectangle(r+2, 2, W-r-2, H-2, fill=COL_BG, outline="")
        c.create_line(r+2,  2, W-r-2,  2, fill=COL_BORDER)
        c.create_line(r+2, H-2, W-r-2, H-2, fill=COL_BORDER)

        # ── State-specific content ───────────────────────────────────────
        if self._state == OverlayState.LISTENING:
            self._draw_listening(c)
        else:
            self._draw_transcribing(c)

        self._phase += (2 * math.pi) / FPS   # one full cycle per second
        self._after_id = self._root.after(1000 // FPS, self._animate)

    # ── Listening state — animated waveform ───────────────────────────

    def _draw_listening(self, c: tk.Canvas) -> None:
        # Red dot + label
        c.create_oval(18, H//2 - 5, 28, H//2 + 5, fill=COL_DOT_REC, outline="")
        c.create_text(36, H//2 - 10, anchor="w",
                      text="Listening…", fill=COL_TEXT,
                      font=("Segoe UI", 9, "bold"))

        # Waveform bars
        total_w = NUM_BARS * BAR_W + (NUM_BARS - 1) * BAR_GAP
        start_x = (W - total_w) // 2 + 10   # slight right offset for the dot

        for i in range(NUM_BARS):
            # Sine wave with per-bar phase offset
            t = math.sin(self._phase + i * (math.pi / (NUM_BARS / 2)))
            bar_h = int(BAR_MIN_H + (t * 0.5 + 0.5) * (BAR_MAX_H - BAR_MIN_H))

            x1 = start_x + i * (BAR_W + BAR_GAP)
            x2 = x1 + BAR_W
            y2 = BAR_BASE_Y
            y1 = y2 - bar_h

            # Interpolate colour: blue (low) → red (high)
            factor = (bar_h - BAR_MIN_H) / (BAR_MAX_H - BAR_MIN_H)
            colour = self._lerp_hex(COL_BAR_LOW, COL_BAR_HIGH, factor)

            # Rounded bar (approximate with small rectangle)
            c.create_rectangle(x1, y1, x2, y2, fill=colour, outline="")

    # ── Transcribing state — pulsing dots ─────────────────────────────

    def _draw_transcribing(self, c: tk.Canvas) -> None:
        c.create_text(W // 2, 18, text="Transcribing…", fill=COL_TEXT,
                      font=("Segoe UI", 9, "bold"))

        dot_r  = 7
        dot_n  = 5
        spacing = 22
        base_x = W // 2 - (dot_n - 1) * spacing // 2
        base_y = 46

        for i in range(dot_n):
            # Staggered phase per dot
            alpha = math.sin(self._phase + i * (2 * math.pi / dot_n))
            size  = int(dot_r * (0.4 + 0.6 * (alpha * 0.5 + 0.5)))
            cx    = base_x + i * spacing
            factor = alpha * 0.5 + 0.5
            colour = self._lerp_hex(COL_BORDER, COL_PULSE, factor)
            c.create_oval(cx - size, base_y - size,
                          cx + size, base_y + size,
                          fill=colour, outline="")

    # ── Colour helpers ─────────────────────────────────────────────────

    @staticmethod
    def _lerp_hex(hex_a: str, hex_b: str, t: float) -> str:
        """Linear interpolation between two hex colours."""
        t = max(0.0, min(1.0, t))
        ra, ga, ba = int(hex_a[1:3],16), int(hex_a[3:5],16), int(hex_a[5:7],16)
        rb, gb, bb = int(hex_b[1:3],16), int(hex_b[3:5],16), int(hex_b[5:7],16)
        r = int(ra + (rb - ra) * t)
        g = int(ga + (gb - ga) * t)
        b = int(ba + (bb - ba) * t)
        return f"#{r:02x}{g:02x}{b:02x}"
