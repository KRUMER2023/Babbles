"""
Smoke test - runs the full audio->transcription pipeline without any UI.
Run with: .venv/Scripts/python.exe smoke_test.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from core.audio import AudioRecorder
from core.transcriber import Transcriber

print("=== Babbles Pipeline Smoke Test ===\n")

# Load configuration
APP_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = APP_DIR / "config.json"

model_size = "base"
device = "cuda"
compute_type = "float16"

if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            config = json.load(f)
            model_config = config.get("model", {})
            model_size = model_config.get("size", "base")
            device = model_config.get("device", "cuda")
            compute_type = model_config.get("compute_type", "float16")
    except Exception as exc:
        print(f"Warning: Failed to load config.json: {exc}")

# 1. Load model
print(f"[1/3] Loading faster-whisper '{model_size}' model on {device} ({compute_type}) from local models/...")
t = Transcriber(
    model_size=model_size,
    device=device,
    compute_type=compute_type,
    download_root=str(APP_DIR / "models")
)
t.load()
print("      Model loaded OK.\n")

# 2. Capture 2 seconds of audio
print("[2/3] Recording 2 seconds of audio from your microphone...")
r = AudioRecorder()
r.start()
time.sleep(2)
audio = r.stop()
print(f"      Captured {len(audio)} samples ({len(audio)/16000:.2f} s)\n")

# 3. Transcribe
print("[3/3] Transcribing...")
result = t.transcribe(audio)

if result:
    print(f"      Result: {result!r}")
else:
    print("      Result: (empty — VAD filtered out silence, which is correct)")

print("\n=== Smoke test PASSED ===")
