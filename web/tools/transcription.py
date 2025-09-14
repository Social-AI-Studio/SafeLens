import os
import logging
import torch
import whisperx

logger = logging.getLogger(__name__)


def _select_device_and_compute_type():
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


def transcribe_whole_video(video_path):
    device, compute_type = _select_device_and_compute_type()
    logger.info(f"Using device: {device} (compute_type={compute_type})")

    model = whisperx.load_model("medium", device=device, compute_type=compute_type)
    audio = whisperx.load_audio(video_path)

    result = model.transcribe(audio, batch_size=16)
    segments = result.get("segments", [])
    full_text = " ".join(seg.get("text", "") for seg in segments)

    word_timestamps = []
    try:
        model_a, metadata = whisperx.load_align_model(
            language_code=result.get("language", "en"), device=device
        )
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
