# Babbles — Architecture Reference

> **Rule:** This document must be updated whenever a module is added, changed, or removed.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (BabblesApp)                     │
│                                                                 │
│  Tk main loop ◄──── overlay.py  ◄──── hotkey callbacks         │
│       │                                     │                   │
│       ├── tray.py (daemon thread)           │                   │
│       ├── settings_ui.py (Toplevel)         │                   │
│       └── hotkey.py (keyboard hook) ────────┘                   │
│                │                                                │
│          on_record_start ──► audio.py ──► start()              │
│          on_record_stop  ──► audio.py ──► stop() → np.ndarray  │
│                                   │                             │
│                            transcriber.py ──► text: str        │
│                                   │                             │
│                             output.py ──► Ctrl+V paste          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Thread Map

| Thread | Name | Purpose |
|---|---|---|
| Main | Tk event loop | Overlay, settings window |
| Daemon | `TrayIcon` | pystray tray icon |
| Daemon | `ModelLoader` | Pre-load Whisper model at startup |
| Daemon | `keyboard` (internal) | OS keyboard hook |
| Daemon | (per keypress) | audio → transcribe → paste pipeline |

---

## Module Reference

### `core/audio.py` — AudioRecorder

| Method | Description |
|---|---|
| `start()` | Opens sounddevice InputStream, begins buffering |
| `stop() → np.ndarray` | Closes stream, returns 1-D float32 array @ 16 kHz |

**Key decisions:**
- Audio is stored in-memory (`self._frames: list[np.ndarray]`) — never written to disk.
- sounddevice callback appends raw frames; concatenation happens only at `stop()`.
- VAD is NOT applied here — delegated to faster-whisper's `vad_filter=True`.

---

### `core/hotkey.py` — HotkeyListener

| Method | Description |
|---|---|
| `set_callbacks(on_start, on_stop)` | Register press/release handlers |
| `start()` | Attach global keyboard hook |
| `stop()` | Remove all hooks |

**Key decisions:**
- Uses `keyboard.hook()` (raw event stream) rather than `keyboard.add_hotkey()` to properly detect press-and-hold vs. single-tap.
- Internal `_recording_mode` state machine tracks `"hold"` vs `"toggle"` states, ignoring `Space` release events during a toggle session.
- `reset_state()` handles out-of-band stops (e.g. from the system tray toggle).
- Callbacks are fired on fresh daemon threads (never block the hook).

---

### `core/transcriber.py` — Transcriber

| Method | Description |
|---|---|
| `load()` | Download + load model into VRAM |
| `transcribe(audio) → str` | Run inference, return plain text |
| `unload()` | Release VRAM |

**Key decisions:**
- `device="cuda"`, `compute_type="float16"` for RTX 2050 performance.
- `vad_filter=True` — faster-whisper's built-in VAD strips silence/noise segments.
- Model is pre-loaded once at startup; `is_ready` gate prevents crashes if hotkey pressed before load completes.
- `beam_size=5` is the default Whisper recommendation (accuracy vs. speed balance).

---

### `core/output.py` — OutputHandler

| Method | Description |
|---|---|
| `paste(text)` | Save clipboard → copy text → Ctrl+V → restore |

**Key decisions:**
- Clipboard approach is ~100× faster than `pyautogui.typewrite()` for long text.
- 60 ms settle delay before Ctrl+V ensures OS clipboard is ready.
- Clipboard restore happens on a daemon thread after `restore_delay_ms` (default 250 ms).

---

### `ui/overlay.py` — ListeningOverlay

| Method | Description |
|---|---|
| `show_listening()` | Display animated waveform (thread-safe) |
| `show_transcribing()` | Switch to pulsing dots (thread-safe) |
| `hide()` | Destroy window (thread-safe) |

**Key decisions:**
- All state changes are posted via `root.after(0, ...)` — tkinter is single-threaded.
- Two-state machine: `LISTENING` (sine waveform bars) / `TRANSCRIBING` (pulsing dots).
- No title bar (`overrideredirect=True`), always-on-top, 93% alpha.
- Pill-shaped dark navy background (`#0d1117`) with red (`#f85149`) / blue (`#58a6ff`) accents.
- Animated at 20 FPS via `root.after(50, ...)` loop.

---

### `ui/tray.py` — TrayApp

Wraps pystray. Loads the transparent Babbles logo from `babbles_logo.ico`. Menu: Toggle Dictation (Dynamic) | Settings | Quit. Runs on a daemon thread. Context menu dynamically retrieves listening state via `is_listening_fn` to switch its label text.

### `ui/settings_ui.py` — SettingsWindow

CustomTkinter Toplevel modal. Exposes: microphone selection (via `sounddevice.query_devices`), model size, device, language, clipboard restore delay, and a show terminal toggle. Calls `on_save` callback; `main.py` writes back to `config.json` and pushes updates live.

---

## Data Flow

```
Ctrl+Space press
   │
   ▼
HotkeyListener._on_key_event()
   │
   ├──► AudioRecorder.start()       ← microphone opens
   └──► ListeningOverlay.show_listening()

Ctrl+Space release
   │
   ▼
HotkeyListener._on_key_event()
   │
   ├──► AudioRecorder.stop() → np.ndarray (float32, 16 kHz)
   ├──► ListeningOverlay.show_transcribing()
   │
   ▼
Transcriber.transcribe(audio) → str
   │
   ├──► ListeningOverlay.hide()
   └──► OutputHandler.paste(text) → Ctrl+V in active window
```

---

## Config Schema (`config.json`)

```jsonc
{
  "model": {
    "size": "small",          // tiny|base|small|medium|large-v3
    "device": "cuda",         // cuda|cpu
    "compute_type": "float16",// float16 (GPU) | int8 (CPU)
    "cpu_fallback_compute_type": "int8",
    "language": "en",         // ISO code or null (auto-detect)
    "beam_size": 5,
    "vad_filter": true
  },
  "audio": { 
    "sample_rate": 16000, 
    "channels": 1, 
    "device": null            // device index (int) or null (default)
  },
  "hotkey": "ctrl+space",
  "toggle_hotkey": "ctrl+alt+space",
  "output": { "clipboard_restore_delay_ms": 250 },
  "ui": { 
    "overlay_position": "bottom_center", 
    "overlay_margin_bottom_px": 40,
    "show_terminal": false
  },
  "logging": { "level": "INFO", "file": "babbles.log" }
}
```
