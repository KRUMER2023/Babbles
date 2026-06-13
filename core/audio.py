"""
core/audio.py
─────────────
Microphone capture via sounddevice.

Audio is recorded at 16 kHz mono into an in-memory NumPy float32 buffer.
VAD (Voice Activity Detection) is handled by faster-whisper's built-in
vad_filter, so no extra dependency is needed here.

Changelog
─────────
v0.1.0 – Initial implementation (sounddevice, in-memory buffer, no disk I/O).
"""

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE: int = 16_000   # Hz  — Whisper requires 16 kHz
CHANNELS:    int = 1         # Mono
DTYPE:       str = "float32"


class AudioRecorder:
    """
    Thread-safe, non-blocking microphone recorder.

    Usage::

        recorder = AudioRecorder()
        recorder.start()          # call on Ctrl+Space press
        audio = recorder.stop()   # call on Ctrl+Space release → np.ndarray
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, device: int | None = None) -> None:
        self.sample_rate   = sample_rate
        self.device        = device
        self.is_recording  = False
        self._frames: list[np.ndarray] = []
        self._lock   = threading.Lock()
        self._stream: sd.InputStream | None = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Begin capturing audio from the configured input device."""
        with self._lock:
            if self.is_recording:
                logger.warning("start() called while already recording — ignored.")
                return
            self._frames.clear()

            # ── Device selection validation ──────────────────────────────────
            active_device = self.device
            if active_device is not None:
                try:
                    devices = sd.query_devices()
                    if active_device < 0 or active_device >= len(devices):
                        logger.warning("Selected audio device index %d is invalid. Falling back to default input.", active_device)
                        active_device = None
                    elif devices[active_device]["max_input_channels"] <= 0:
                        logger.warning("Selected audio device index %d is not an input device. Falling back to default input.", active_device)
                        active_device = None
                except Exception as exc:
                    logger.warning("Failed to validate selected audio device: %s. Falling back to default input.", exc)
                    active_device = None

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    callback=self._sd_callback,
                    device=active_device,
                )
                self._stream.start()
                self.is_recording = True
                logger.info("🎙 Recording started (device: %s).", "default" if active_device is None else active_device)
            except Exception as exc:
                logger.error("Failed to start sounddevice InputStream: %s", exc, exc_info=True)
                self.is_recording = False
                self._stream = None

    def stop(self) -> np.ndarray:
        """
        Stop capturing and return the audio as a 1-D float32 array at
        ``self.sample_rate`` Hz.  Returns an empty array if nothing was captured.
        """
        with self._lock:
            if not self.is_recording:
                logger.warning("stop() called while not recording — returning empty.")
                return np.zeros(0, dtype=DTYPE)

            self.is_recording = False
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            if not self._frames:
                logger.warning("No audio frames were captured.")
                return np.zeros(0, dtype=DTYPE)

            audio = np.concatenate(self._frames, axis=0).flatten()
            
            # ── Software Gain & Peak Normalisation ───────────────────────────
            # Laptop mics are notoriously quiet. We scale the signal so the peak
            # absolute value reaches 0.95, giving Whisper a loud and clear input.
            max_val = np.max(np.abs(audio)) if len(audio) > 0 else 0.0
            if max_val > 0.01:
                audio = audio * (0.95 / max_val)
                logger.info("🔊 Audio normalized: original peak was %.3f, boosted to 0.95", max_val)
            else:
                logger.debug("Audio too quiet (peak: %.3f) — skipping normalization to avoid amplifying static.", max_val)

            duration = len(audio) / self.sample_rate
            logger.info("✅ Recording stopped — %.2f s captured.", duration)
            return audio

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _sd_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.debug("sounddevice callback status: %s", status)
        if self.is_recording:
            self._frames.append(indata.copy())
