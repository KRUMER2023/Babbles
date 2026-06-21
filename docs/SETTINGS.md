# Babbles Settings

The Babbles application provides a convenient settings panel accessible via the tray icon. This document explains each available setting in detail to help you configure the application to your needs.

## 1. Microphone
**Description:** Selects the audio input device used for recording your speech.
* **Options:** `Default` (uses your operating system's default recording device) or a specific microphone connected to your system.
* **Usage:** If you have multiple microphones (e.g., a webcam mic and a headset), use this setting to explicitly choose which one Babbles should listen to.

## 2. Whisper Model
**Description:** Determines the size of the underlying speech-to-text model (`faster-whisper`) that transcribes your audio.
* **Options:** `tiny`, `base`, `small`, `medium`, `large-v3`
* **Usage:** 
  * `tiny` / `base`: Fastest transcription speed and lowest memory usage, but slightly less accurate. Good for older hardware.
  * `small`: A great balance between speed and accuracy. Recommended for most users.
  * `medium` / `large-v3`: Highest accuracy, but slower and requires significantly more RAM/VRAM. Best if you have a powerful dedicated GPU.

## 3. Device
**Description:** Specifies the hardware used to run the transcription model.
* **Options:** `cuda`, `cpu`
* **Usage:** 
  * `cuda`: Runs the model on your NVIDIA GPU using hardware acceleration. This is significantly faster and is highly recommended. *(Note: Requires an NVIDIA GPU and proper CUDA libraries).*
  * `cpu`: Runs the model on your computer's main processor. Slower than CUDA, but works on any machine regardless of the graphics card. The app will automatically fallback to CPU if CUDA fails to load.

## 4. Language
**Description:** Sets the language you will be speaking.
* **Options:** `en` (English), `auto` (Auto-detect), `fr` (French), `de` (German), `es` (Spanish), `pt` (Portuguese), `ja` (Japanese), `zh` (Chinese).
* **Usage:** Setting a specific language (like `en`) speeds up transcription and improves accuracy because the model doesn't have to spend time guessing the language first. Use `auto` if you speak multiple languages interchangeably.

## 5. Clipboard Restore (ms)
**Description:** The time (in milliseconds) the app waits before restoring your previous clipboard content.
* **Usage:** Babbles works by quickly copying the transcribed text to your clipboard, simulating a "Paste" command, and then putting your original clipboard content back. If this delay is too short, the app might paste your old clipboard content instead of the transcribed text. If it's too long, you might accidentally paste the transcribed text elsewhere. **Default is usually 250ms.** Increase this slightly if your PC is slow and pastes the wrong text.

## 6. Show Terminal
**Description:** Toggles the visibility of the background console/terminal window.
* **Usage:** When enabled, a black terminal window will appear showing live application logs, errors, and background processes. This is mostly useful for debugging or monitoring performance. Turn this off for a cleaner, silent background experience.
