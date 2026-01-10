import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _check_nltk_punkt() -> Dict[str, Any]:
    try:
        import nltk

        for resource in ("tokenizers/punkt_tab", "tokenizers/punkt"):
            try:
                nltk.data.find(resource)
                return {"ok": True, "resource": resource}
            except LookupError:
                continue
        return {
            "ok": False,
            "error": "punkt_not_found",
            "NLTK_DATA": os.getenv("NLTK_DATA"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def warmup_providers() -> Dict[str, Any]:
    """
    Best-effort warmup for heavyweight providers so the first user request isn't
    blocked by downloads/initialization.
    """
    started = time.time()

    details: Dict[str, Any] = {}

    # WhisperX (transcription)
    try:
        from ...tools.transcription import warmup_whisperx

        details["transcription"] = warmup_whisperx()
    except Exception as e:
        details["transcription"] = {"ok": False, "error": str(e)}

    # OCR (EasyOCR/Tesseract)
    try:
        from ...tools.ocr import warmup_ocr

        details["ocr"] = warmup_ocr()
    except Exception as e:
        details["ocr"] = {"ok": False, "error": str(e)}

    # NLTK (sentence tokenizer)
    details["nltk"] = _check_nltk_punkt()

    details["elapsed_ms"] = int((time.time() - started) * 1000)
    return details

