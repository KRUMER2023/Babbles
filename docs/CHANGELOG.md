# Babbles — Changelog

> All changes, optimisations, and new features are recorded here.
> Format: `## [vX.Y.Z] — YYYY-MM-DD`

---

## [v0.2.1] — 2026-06-13

### 🎨 UI & Developer Testing Improvements

**Tray Icon Brand Identity (`ui/tray.py`):**
- Replaced the programmatically drawn microphone icon in the system tray with the official transparent Babbles logo (`babbles_logo.ico`) loaded locally.
- Retained the old `_make_icon` method in the code for compatibility/fallback reference.

**Local Offline Smoke Test (`smoke_test.py`):**
- Fixed the offline smoke test to load from the local `models/` directory instead of default C drive cache.
- Made the smoke test automatically query and use the model configuration (size, device, compute type) specified in `config.json` rather than hardcoding `"base"`.

---

## [v0.2.0] — 2026-05-20

### 🎙 Quality of Life & UI Enhancements

**Microphone Selection (`core/audio.py`, `ui/settings_ui.py`):**
- Added a dynamic dropdown in the Settings window to query and select specific audio input devices.
- Changes take effect immediately without requiring an application restart.
- Includes a safety fallback to the system default microphone if the selected device is unplugged.

**Dictation Toggle Mode (`core/hotkey.py`, `ui/tray.py`):**
- Added `Ctrl+Alt+Space` as a global hotkey to cleanly toggle dictation on/off (alternative to press-and-hold `Ctrl+Space`).
- Added a dynamic "Start Dictation" / "Stop Listening" button to the system tray context menu.
- Safe state tracking ensures UI and keyboard hooks remain perfectly synchronized.

**Terminal Visibility Toggle (`main.py`, `ui/settings_ui.py`):**
- Added a "Show Terminal" toggle in Settings to hide the command prompt window during runtime.
- Instantly hides/shows the console via Windows API (`ctypes.windll.user32.ShowWindow`).
- Cleanly restores terminal visibility on exit so batch launcher pauses remain visible.

---

## [v0.1.5] — 2026-05-20

### 🔊 Transcription Accuracy Optimizations

**Microphone Software gain & Peak Normalisation (`core/audio.py`):**
- Automatically scales and normalizes the peak amplitude of recorded voice inputs to `0.95`.
- Boosts quiet or distant laptop microphone speech signals instantly before sending to CTranslate2.
- Employs a `0.01` noise-gate guard to prevent amplifying pure ambient room hiss or fan noise.

**Whisper Model Upgrade (`config.json`):**
- Upgraded the default Whisper model size from `"base"` (74M parameters) to `"small"` (244M parameters) to deliver substantially better word-boundary accuracy and homophone recognition.

**Voice Activity Detection (VAD) Tuning (`core/transcriber.py`):**
- Configured a lower `threshold = 0.38` (previously `0.5`) to capture faint syllables without clipping them.
- Increased `speech_pad_ms = 500` (previously `400ms`) to preserve breathy word endings.

---

## [v0.1.4] — 2026-05-19

### 🚀 Quality of Life — Auto-Elevating Batch Launcher

**Added `run_babbles.bat`:**
- A simple double-click launcher created at the project root.
- **Auto-Elevation:** Automatically detects if running with Admin privileges. If not, it requests elevation through PowerShell, removing the need to right-click -> "Run as Administrator".
- **Venv Target:** Executes `main.py` directly using `.venv\Scripts\python.exe` so you don't have to manually activate the virtual environment beforehand.

---

## [v0.1.3] — 2026-05-19

### 🐛 Bug Fix — cublas64_12.dll Not Found (CUDA Runtime Missing)

**Root cause:** CTranslate2 requires CUDA 12 runtime DLLs (`cublas64_12.dll`, etc.) to be present on `PATH` or bundled. The RTX 2050 driver was detected (1 CUDA device visible) but the CUDA Toolkit was not installed, so cuBLAS DLL was missing.

**Fix in `core/transcriber.py`:**
- Added `_is_cuda_dll_error()` helper to detect missing CUDA DLL errors
- `load()` now catches `RuntimeError` with CUDA DLL keywords and automatically retries with `device="cpu"`, `compute_type="int8"`
- `transcribe()` also catches CUDA DLL errors mid-inference and retries on CPU
- Active device/compute_type tracked via `_active_device` / `_active_compute_type` attributes
- Clear warning logged with pip fix command when fallback triggers

**Config change (`config.json`):**
- Added `cpu_fallback_compute_type` field (default: `"int8"`)

**To restore GPU acceleration (optional):**
Install CUDA 12 Toolkit from https://developer.nvidia.com/cuda-downloads (select Windows, x86_64, your OS version, exe installer).

---



### 🐛 Bug Fix — Tcl/Tk Not Found When Running as Administrator

**Root cause:** Windows strips user-level environment variables (`TCL_LIBRARY`, `TK_LIBRARY`) when a process runs elevated (as Administrator). The `keyboard` library requires admin privileges, but tkinter then cannot find `init.tcl`.

**Fix applied in `main.py`:**
- Added `_fix_tcl_tk()` function that runs **before any tkinter import**
- Reads `pyvenv.cfg` `home` key to locate the real Python base directory
- Scans `<python_base>/tcl/` for `tcl8.x` (validated by `init.tcl` presence) and `tk8.x` (validated by `tk.tcl` presence)
- Sets `TCL_LIBRARY` and `TK_LIBRARY` via `os.environ.setdefault()` — only if not already set
- Uses `sorted(..., reverse=True)` to prefer `tcl8.6` over bare `tcl8` module folder
- Tested: `TCL_LIBRARY = .../tcl8.6`, `TK_LIBRARY = .../tk8.6` — `tk.Tk()` succeeds

---



### ✅ Environment Verified

- Confirmed Python **3.13.0** is compatible with all 8 dependencies
- `ctranslate2 4.7.1` detects **1 CUDA device** (RTX 2050) — GPU path confirmed
- Smoke test passed:
  - `base` Whisper model downloaded and loaded on CUDA
  - 1.98 s audio buffer captured correctly (31,616 samples @ 16 kHz)
  - VAD correctly filtered silence → empty result (expected behaviour)
- Added `smoke_test.py` for repeatable pipeline verification
- Fixed `SyntaxWarning` for backslash escape sequence in `smoke_test.py` docstring
- **Note:** HuggingFace symlinks warning is non-critical; model caches fine without symlinks

---


## [v0.1.0] — 2026-05-18

### 🎉 Initial Implementation

#### Project Scaffolding
- Created full directory structure: `core/`, `ui/`, `docs/`
- Added `.gitignore` (Python, venv, IDE, OS, model cache)
- Added `requirements.txt` with pinned dependencies
- Added `config.json` with default settings

#### Core Modules
- **`core/audio.py`** — In-memory microphone capture via sounddevice at 16 kHz mono; no disk I/O
- **`core/hotkey.py`** — Global `Ctrl+Space` press-and-hold detector using `keyboard.hook()`; callbacks on daemon threads
- **`core/transcriber.py`** — faster-whisper local engine; CUDA float16 on RTX 2050; `base` model; built-in VAD filter; pre-loaded at startup
- **`core/output.py`** — Clipboard-based text injection (save → Ctrl+V → restore); 60 ms settle + 250 ms restore delay

#### UI
- **`ui/overlay.py`** — Animated pill overlay at screen bottom centre; two states: Listening (sine waveform bars) and Transcribing (pulsing dots); 20 FPS; thread-safe via `root.after()`
- **`ui/tray.py`** — System-tray icon with programmatic microphone icon (Pillow); Settings / Quit menu
- **`ui/settings_ui.py`** — CustomTkinter modal settings window; model size, device, language, clipboard delay

#### Entry Point
- **`main.py`** — Full pipeline integration; BabblesApp class; model pre-load on daemon thread; Tk main loop

#### Architecture Decisions
- `webrtcvad` removed — replaced by faster-whisper's built-in `vad_filter=True` (avoids Python 3.13 wheel issues)
- `openai` package removed — local-only mode
- Overlay built with tkinter stdlib (no extra dependency)
- All thread-to-UI communication via `root.after(0, ...)` (tkinter thread safety)

#### Documentation
- `docs/README.md` — Project overview, features, quick start
- `docs/ARCHITECTURE.md` — Full architecture, thread map, module reference, data flow
- `docs/SETUP.md` — Step-by-step setup guide, troubleshooting
- `docs/CHANGELOG.md` — This file

---

*Next: venv creation, dependency install, first smoke test.*
