import os
import logging
import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

import torch
import whisperx

logger = logging.getLogger(__name__)

_WHISPERX_LOCK = threading.Lock()
_WHISPERX_MODEL = None
_WHISPERX_MODEL_CFG: Optional[Tuple[str, str, str]] = None  # (model_name, device, compute_type)

_ALIGN_LOCK = threading.Lock()
_ALIGN_CACHE: Dict[Tuple[str, str], Tuple[Any, Any]] = {}  # (language_code, device) -> (model, metadata)

_TRANSCRIBE_SEM_LOCK = threading.Lock()
_TRANSCRIBE_SEM: Optional[threading.Semaphore] = None
_TRANSCRIBE_SEM_CFG: Optional[int] = None


def _select_device_and_compute_type() -> Tuple[str, str]:
    """Select WhisperX device and compute type safely.

    - Prefer CUDA if available (and not explicitly disabled).
    - On CUDA: default compute_type=float16 (configurable via WHISPER_COMPUTE_TYPE).
    - On CPU: force compute_type=int8 to avoid float16 errors.
    - Allow override via env vars: WHISPER_DEVICE, WHISPER_COMPUTE_TYPE.
    """
    env_device = os.getenv("WHISPER_DEVICE") or os.getenv("TRANSCRIBE_DEVICE")
    cuda_available = torch.cuda.is_available()

    if env_device == "cuda" and not cuda_available:
        logger.warning(
            "WHISPER_DEVICE=cuda requested but CUDA is not available; falling back to cpu"
        )

    if (env_device == "cuda" and cuda_available) or (
        env_device is None and cuda_available
    ):
        device = "cuda"
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
    else:
        device = "cpu"
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    return device, compute_type


def _get_transcribe_semaphore() -> Optional[threading.Semaphore]:
    """Get a process-wide semaphore limiting concurrent WhisperX work.

    Default is 1 (serialize). Set WHISPER_MAX_CONCURRENT=0 to disable limiting.
    """
    global _TRANSCRIBE_SEM, _TRANSCRIBE_SEM_CFG

    try:
        max_concurrent = int(os.getenv("WHISPER_MAX_CONCURRENT", "1"))
    except Exception:
        max_concurrent = 1

    if max_concurrent <= 0:
        return None

    with _TRANSCRIBE_SEM_LOCK:
        if _TRANSCRIBE_SEM is None or _TRANSCRIBE_SEM_CFG != max_concurrent:
            _TRANSCRIBE_SEM = threading.Semaphore(max_concurrent)
            _TRANSCRIBE_SEM_CFG = max_concurrent
        return _TRANSCRIBE_SEM


@contextmanager
def _whisperx_concurrency_guard():
    sem = _get_transcribe_semaphore()
    if sem is None:
        yield
        return
    sem.acquire()
    try:
        yield
    finally:
        sem.release()


def _get_whisperx_model(model_name: str, device: str, compute_type: str):
    """Load WhisperX model once per process for the selected (model, device, compute_type)."""
    global _WHISPERX_MODEL, _WHISPERX_MODEL_CFG

    cfg = (model_name, device, compute_type)
    if _WHISPERX_MODEL is not None and _WHISPERX_MODEL_CFG == cfg:
        return _WHISPERX_MODEL

    with _WHISPERX_LOCK:
        if _WHISPERX_MODEL is not None and _WHISPERX_MODEL_CFG == cfg:
            return _WHISPERX_MODEL

        logger.info(
            f"Loading WhisperX model: {model_name} (device={device}, compute_type={compute_type})"
        )
        _WHISPERX_MODEL = whisperx.load_model(
            model_name, device=device, compute_type=compute_type
        )
        _WHISPERX_MODEL_CFG = cfg
        return _WHISPERX_MODEL


def _get_align_model(language_code: str, device: str):
    """Cache align model per (language_code, device) to avoid repeated loads."""
    key = (language_code or "en", device)
    cached = _ALIGN_CACHE.get(key)
    if cached is not None:
        return cached

    with _ALIGN_LOCK:
        cached = _ALIGN_CACHE.get(key)
        if cached is not None:
            return cached
        model_a, metadata = whisperx.load_align_model(language_code=key[0], device=device)
        _ALIGN_CACHE[key] = (model_a, metadata)
        return model_a, metadata


def warmup_whisperx() -> Dict[str, Any]:
    """Eagerly load WhisperX to avoid first-request downloads/initialization."""
    device, compute_type = _select_device_and_compute_type()
    model_name = os.getenv("WHISPER_MODEL", "large-v2")
    with _whisperx_concurrency_guard():
        _get_whisperx_model(model_name, device, compute_type)
    return {"ok": True, "model": model_name, "device": device, "compute_type": compute_type}


def transcribe_whole_video(video_path: str) -> Dict[str, Any]:
    device, compute_type = _select_device_and_compute_type()
    logger.info(f"Using device: {device} (compute_type={compute_type})")

    model_name = os.getenv("WHISPER_MODEL", "large-v2")
    logger.info(f"Using Whisper model: {model_name}")

    with _whisperx_concurrency_guard():
        model = _get_whisperx_model(model_name, device, compute_type)
        audio = whisperx.load_audio(video_path)

        result = model.transcribe(audio, batch_size=16)
        segments = result.get("segments", [])
        full_text = " ".join(seg.get("text", "") for seg in segments)

        word_timestamps = []
        try:
            language_code = result.get("language", "en")
            model_a, metadata = _get_align_model(language_code, device)
            result_aligned = whisperx.align(
                segments, model_a, metadata, audio, device, return_char_alignments=False
            )
            for segment in result_aligned.get("segments", []) or []:
                for word in segment.get("words", []) or []:
                    w = word.get("word", "")
                    s = word.get("start", segment.get("start", 0.0))
                    if w:
                        word_timestamps.append((w, s))
        except Exception as e:
            logger.warning(f"Alignment failed: {str(e)} - using segment-level timestamps")
            for segment in segments:
                txt = segment.get("text", "")
                if txt:
                    word_timestamps.append((txt, segment.get("start", 0.0)))

        logger.info(f"Transcription complete. Words: {len(word_timestamps)}")
        return {
            "full_text": full_text,
            "word_timestamps": word_timestamps,
        }
