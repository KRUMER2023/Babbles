"""
core/transcriber.py
───────────────────
Wraps faster-whisper for local speech recognition.

Optimisations applied
─────────────────────
* Model is pre-loaded once at startup (no per-request cold start).
* CUDA + float16 leverages RTX 2050 when CUDA runtime DLLs are present.
* Auto-fallback: if CUDA runtime DLLs are missing (e.g. cublas64_12.dll),
  the transcriber automatically retries with CPU + int8 so the app keeps
  working without manual config changes.
* faster-whisper's built-in vad_filter suppresses hallucinations from silence.
* beam_size=5 balances accuracy vs. speed for the base model.

Changelog
─────────
v0.1.0 – Initial implementation (faster-whisper, CUDA, vad_filter, base model).
v0.1.2 – Added CUDA-to-CPU auto-fallback for missing cublas/CUDA runtime DLLs.
"""

from __future__ import annotations

import logging
from typing import Iterator

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment

logger = logging.getLogger(__name__)

# Substrings that indicate a missing CUDA runtime library
_CUDA_DLL_ERRORS = ("cublas", "cudnn", "cufft", "curand", "cusolver",
                    "cusparse", "cuda runtime", "cannot be loaded",
                    "not found or cannot be loaded")


def _is_cuda_dll_error(exc: Exception) -> bool:
    """Return True if the exception is caused by a missing CUDA DLL."""
    msg = str(exc).lower()
    return any(kw in msg for kw in _CUDA_DLL_ERRORS)


class Transcriber:
    """
    Local Whisper transcription engine backed by faster-whisper + CTranslate2.

    Parameters
    ----------
    model_size:    Whisper model variant — ``tiny | base | small | medium | large-v3``.
    device:        ``"cuda"`` (GPU) or ``"cpu"``.
    compute_type:  ``"float16"`` for GPU, ``"int8"`` for CPU.
    language:      ISO-639 code, e.g. ``"en"``.  ``None`` = auto-detect.
    beam_size:     Beam search width.  Higher → more accurate, slower.
    vad_filter:    Enable faster-whisper's built-in VAD to skip silence.
    """

    def __init__(
        self,
        model_size:    str       = "base",
        device:        str       = "cuda",
        compute_type:  str       = "float16",
        language:      str | None = "en",
        beam_size:     int       = 5,
        vad_filter:    bool      = True,
        download_root: str | None = None,
    ) -> None:
        self.model_size    = model_size
        self.device        = device
        self.compute_type  = compute_type
        self.language      = language
        self.beam_size     = beam_size
        self.vad_filter    = vad_filter
        self.download_root = download_root
        self._model: WhisperModel | None = None
        self._active_device       = device        # may be changed by fallback
        self._active_compute_type = compute_type  # may be changed by fallback

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """
        Download (first run) and load the Whisper model into VRAM/RAM.

        If CUDA runtime DLLs are missing, automatically falls back to
        CPU + int8 and logs a clear warning with fix instructions.

        This is intentionally blocking — call once from a background thread
        at startup so the first hotkey press has zero model-load latency.
        """
        logger.info(
            "Loading faster-whisper model '%s' on %s (%s)…",
            self.model_size, self._active_device, self._active_compute_type,
        )
        try:
            self._model = WhisperModel(
                self.model_size,
                device=self._active_device,
                compute_type=self._active_compute_type,
                download_root=self.download_root,
            )
            logger.info("✅ Model loaded and ready on %s.", self._active_device.upper())

        except (RuntimeError, Exception) as exc:
            if self._active_device == "cuda" and _is_cuda_dll_error(exc):
                logger.warning(
                    "⚠️  CUDA runtime DLL missing (%s).\n"
                    "    Falling back to CPU + int8 automatically.\n"
                    "    To fix GPU acceleration, run:\n"
                    "        pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12\n"
                    "    or install the CUDA 12 Toolkit from https://developer.nvidia.com/cuda-downloads",
                    exc,
                )
                self._active_device       = "cpu"
                self._active_compute_type = "int8"
                self._model = WhisperModel(
                    self.model_size,
                    device=self._active_device,
                    compute_type=self._active_compute_type,
                    download_root=self.download_root,
                )
                logger.info(
                    "✅ Model loaded on CPU (int8). Transcription will work "
                    "but will be slower than GPU. Install CUDA 12 DLLs to re-enable GPU."
                )
            else:
                logger.error("Failed to load model: %s", exc, exc_info=True)
                raise

    def unload(self) -> None:
        """Release the model from VRAM/RAM."""
        self._model = None
        logger.info("Model unloaded.")

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def active_device(self) -> str:
        """The device actually in use (may differ from requested if CUDA fell back)."""
        return self._active_device

    # ------------------------------------------------------------------ #
    #  Transcription                                                       #
    # ------------------------------------------------------------------ #

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Convert a 1-D float32 NumPy array (16 kHz, mono) to text.

        Returns an empty string if the audio is silent or too short.

        Raises RuntimeError if the model has not been loaded yet.
        """
        if self._model is None:
            raise RuntimeError("Model is not loaded. Call load() first.")

        if len(audio) < 1600:   # < 0.1 s — skip obvious non-speech
            logger.debug("Audio too short (<0.1 s) — skipping transcription.")
            return ""

        logger.info(
            "Transcribing %.2f s of audio on %s…",
            len(audio) / 16_000, self._active_device.upper(),
        )

        # ── Optimized VAD Parameters ─────────────────────────────────────
        # Tuned to capture quiet built-in laptop microphones accurately.
        vad_params = {
            "threshold": 0.38,      # lower threshold (default 0.5) is more sensitive to quiet speech
            "speech_pad_ms": 500,   # longer tail (default 400ms) preserves breathy word endings
        } if self.vad_filter else None

        try:
            segments: Iterator[Segment]
            segments, _info = self._model.transcribe(
                audio,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                vad_parameters=vad_params,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()

        except (RuntimeError, Exception) as exc:
            if self._active_device == "cuda" and _is_cuda_dll_error(exc):
                # CUDA failed at inference time (rare — usually caught at load())
                logger.warning(
                    "CUDA error during transcription — retrying on CPU: %s", exc
                )
                self._active_device       = "cpu"
                self._active_compute_type = "int8"
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=self.download_root,
                )
                segments, _info = self._model.transcribe(
                    audio,
                    language=self.language,
                    beam_size=self.beam_size,
                    vad_filter=self.vad_filter,
                    vad_parameters=vad_params,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
            else:
                raise

        logger.info("📝 Result: %r", text)
        return text
