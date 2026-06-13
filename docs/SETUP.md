# Babbles — Setup Guide

## Prerequisites

| Requirement | Version |
|---|---|
| Python | **3.11 or 3.12** (strongly recommended — see note below) |
| NVIDIA GPU | RTX 2050 or newer |
| CUDA Toolkit | 11.8 or 12.x |
| Git | Any recent version |

> ⚠️ **Python 3.13 / 3.14 note**: CTranslate2 (used by faster-whisper) may not have pre-built wheels for Python 3.13/3.14 yet. **Python 3.11 is the safest choice.** Use `py -3.11` to create your venv if you have multiple versions installed.

---

## Step 1 — Create the Virtual Environment

> 🔴 **Do this yourself** — Babbles will never create or activate your venv automatically.

Open a terminal in `e:\GIT\Babbles\` and run:

```powershell
# Recommended — Python 3.11
py -3.11 -m venv .venv

# Or Python 3.12 if you don't have 3.11
py -3.12 -m venv .venv
```

---

## Step 2 — Activate the venv

```powershell
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your prompt.

---

## Step 3 — Install CUDA-enabled PyTorch (for faster-whisper GPU support)

faster-whisper uses CTranslate2 which bundles its own CUDA runtime — **no separate PyTorch install is needed** unless you want it for other tools.

Install the dependencies:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

> If you see a CUDA error at runtime, install the matching CTranslate2 CUDA wheel:
> ```
> pip install ctranslate2 --extra-index-url https://download.pytorch.org/whl/cu118
> ```

---

## Step 4 — First Run

```powershell
# Must be run as Administrator for global hotkey detection
python main.py
```

On first launch, Babbles loads the Whisper model directly from the local `models/` folder (which contains pre-downloaded `base` and `small` models). The default model size is `small` (~480 MB), which loads instantly and runs fully offline.

---

## Configuration

Edit `config.json` to change:

| Key | Description | Default |
|---|---|---|
| `model.size` | `tiny / base / small / medium` | `small` |
| `model.device` | `cuda` or `cpu` | `cuda` |
| `model.language` | ISO code or `null` for auto | `en` |
| `output.clipboard_restore_delay_ms` | ms before clipboard restored | `250` |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `keyboard` won't hook | Run terminal / Python as Administrator |
| CUDA out of memory | Switch to `tiny` model or `cpu` device |
| No audio captured | Check default microphone in Windows Sound settings |
| Paste doesn't work | Increase `clipboard_restore_delay_ms` to `400` |
