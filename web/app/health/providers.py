import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def check_llm_health() -> Dict[str, Any]:
    """
    Check LLM provider health with minimal overhead.

    Returns:
        Dict with 'ok' status and 'backend' info
    """
    try:
        backend = os.getenv("ANALYSIS_LLM_BACKEND", "openrouter")

        openrouter_key_present = bool(os.getenv("OPENROUTER_API_KEY"))
        http_url_present = bool(os.getenv("ANALYSIS_LLM_HTTP_URL"))

        base_result = {
            "backend": backend,
            "openrouter_key_present": openrouter_key_present,
            "http_url_present": http_url_present,
            "model": os.getenv("ANALYSIS_LLM_MODEL", "SafeLens/llama-3-8b"),
        }

        if backend == "openrouter":
            if not openrouter_key_present:
                return {
                    **base_result,
                    "ok": False,
                    "error": "OPENROUTER_API_KEY not configured",
                    "note": "OpenRouter backend requires API key configuration",
                }

            return {**base_result, "ok": True}

        elif backend == "http":
            if not http_url_present:
                return {
                    **base_result,
                    "ok": False,
                    "error": "ANALYSIS_LLM_HTTP_URL not configured",
                }

            return {
                **base_result,
                "ok": True,
                "base_url": os.getenv("ANALYSIS_LLM_HTTP_URL"),
            }
        else:
            return {**base_result, "ok": False, "error": f"Unknown backend: {backend}"}

    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return {
            "ok": False,
            "backend": "unknown",
            "openrouter_key_present": bool(os.getenv("OPENROUTER_API_KEY")),
            "http_url_present": bool(os.getenv("ANALYSIS_LLM_HTTP_URL")),
            "error": str(e),
        }


async def check_vision_health() -> Dict[str, Any]:
    """
    Check Qwen HTTP vision provider health via vLLM /models endpoint.
    """
    import requests

    base_url = os.getenv("QWEN_VLLM_BASE_URL", "http://localhost:8001/v1").rstrip("/")
    model = os.getenv("QWEN_VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
    api_key = os.getenv("QWEN_VLLM_API_KEY")
    timeout = float(os.getenv("QWEN_VLLM_TIMEOUT_SEC", "5"))

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(f"{base_url}/models", headers=headers, timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json()
                models = [
                    m.get("id") for m in data.get("data", []) if isinstance(m, dict)
                ]
                present = (model in models) if models else True
                return {
                    "ok": True and present,
                    "backend": "qwen_http",
                    "base_url": base_url,
                    "model": model,
                    "models": models,
                }
            except Exception:
                return {
                    "ok": True,
                    "backend": "qwen_http",
                    "base_url": base_url,
                    "model": model,
                }
        else:
            return {
                "ok": False,
                "backend": "qwen_http",
                "base_url": base_url,
                "model": model,
                "error": f"HTTP {resp.status_code}",
            }
    except Exception as e:
        logger.error(f"Vision (Qwen HTTP) health check failed: {e}")
        return {
            "ok": False,
            "backend": "qwen_http",
            "base_url": base_url,
            "model": model,
            "error": str(e),
        }


async def check_ocr_health() -> Dict[str, Any]:
    """
    Check OCR provider health and detect active backend.

    Returns:
        Dict with 'ok' status and 'backend' info (easyocr or tesseract)
    """
    try:
        from ...tools.ocr import run_ocr

        try:
            import easyocr

            backend = "easyocr"
        except ImportError:
            backend = "tesseract"

        return {"ok": True, "backend": backend}

    except ImportError as e:
        logger.error(f"OCR import failed: {e}")
        return {"ok": False, "backend": "unknown", "error": f"Import failed: {str(e)}"}
    except Exception as e:
        logger.error(f"OCR health check failed: {e}")
        return {"ok": False, "backend": "unknown", "error": str(e)}


async def check_transcription_health() -> Dict[str, Any]:
    """
    Check transcription provider health (import and device test).

    Returns:
        Dict with 'ok' status and device info
    """
    try:
        from ...tools.transcription import transcribe_whole_video

        try:
            import whisperx
        except ImportError:
            return {
                "ok": False,
                "backend": "whisperx",
                "error": "WhisperX not installed",
            }

        device = "cpu"
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
        except ImportError:
            pass

        return {"ok": True, "backend": "whisperx", "device": device}

    except Exception as e:
        logger.error(f"Transcription health check failed: {e}")
        return {"ok": False, "backend": "whisperx", "error": str(e)}


async def check_ffmpeg_health() -> Dict[str, Any]:
    """
    Check ffmpeg availability for clip transcription.

    Returns:
        Dict with 'ok' status and binary path
    """
    try:
        import subprocess

        ffmpeg_binary = os.getenv("FFMPEG_BINARY", "ffmpeg")

        result = subprocess.run(
            [ffmpeg_binary, "-version"], capture_output=True, timeout=5, text=True
        )

        if result.returncode == 0:
            version_line = (
                result.stdout.split("\n")[0] if result.stdout else "unknown version"
            )
            return {
                "ok": True,
                "backend": "ffmpeg",
                "binary": ffmpeg_binary,
                "version": version_line,
            }
        else:
            return {
                "ok": False,
                "backend": "ffmpeg",
                "binary": ffmpeg_binary,
                "error": f"Non-zero exit code: {result.returncode}",
            }

    except FileNotFoundError:
        return {
            "ok": False,
            "backend": "ffmpeg",
            "binary": ffmpeg_binary,
            "error": "Binary not found",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "backend": "ffmpeg",
            "binary": ffmpeg_binary,
            "error": "Command timeout",
        }
    except Exception as e:
        logger.error(f"FFmpeg health check failed: {e}")
        return {"ok": False, "backend": "ffmpeg", "error": str(e)}


async def get_providers_health() -> Dict[str, Any]:
    """
    Get health status for all providers.

    Returns:
        Dict with overall status and individual provider statuses
    """
    logger.info("Running provider health checks")

    # Run all health checks
    llm_health = await check_llm_health()
    vision_health = await check_vision_health()
    ocr_health = await check_ocr_health()
    transcription_health = await check_transcription_health()
    ffmpeg_health = await check_ffmpeg_health()

    providers = {
        "llm": llm_health,
        "vision": vision_health,
        "ocr": ocr_health,
        "transcription": transcription_health,
        "ffmpeg": ffmpeg_health,
    }

    all_ok = all(provider["ok"] for provider in providers.values())

    failed_count = sum(1 for provider in providers.values() if not provider["ok"])

    if all_ok:
        status = "ok"
    elif failed_count <= 2:
        status = "degraded"
    else:
        status = "unhealthy"

    return {
        "status": status,
        "providers": providers,
        "summary": {
            "total": len(providers),
            "healthy": len(providers) - failed_count,
            "failed": failed_count,
        },
    }
