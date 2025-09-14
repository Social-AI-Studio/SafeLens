import os
import io
import time
import base64
import logging
from typing import List, Dict, Any
from PIL import Image
import requests

logger = logging.getLogger(__name__)


def _encode_image_to_data_url(image_path: str) -> str:
    """Load image, encode as JPEG base64 data URL."""
    with Image.open(image_path).convert("RGB") as img:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _build_payload(data_url: str) -> Dict[str, Any]:
    prompt = os.getenv(
        "QWEN_VLLM_CAPTION_PROMPT",
        "Describe every visible element in this frame with maximum detail and objectivity. Include all people/objects/text/environment with precise appearance, position, color, and composition. Avoid guesses; only state what is literally visible.",
    )
    model = os.getenv("QWEN_VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
    temperature = float(os.getenv("QWEN_VLLM_TEMPERATURE", "0.1"))
    max_tokens = int(os.getenv("QWEN_VLLM_MAX_TOKENS", "1024"))
    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }


def _post_chat_completions(payload: Dict[str, Any]) -> str:
    base_url = os.getenv("QWEN_VLLM_BASE_URL", "http://localhost:8193/v1")
    api_key = os.getenv("QWEN_VLLM_API_KEY", None)
    timeout = float(os.getenv("QWEN_VLLM_TIMEOUT_SEC", "20"))

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    t0 = time.time()
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    latency_ms = int((time.time() - t0) * 1000)
    try:
        resp.raise_for_status()
    except Exception as e:
        logger.warning(
            f"Qwen HTTP caption request failed: status={resp.status_code} latency_ms={latency_ms} error={e}"
        )
        return "(caption unavailable)"

    try:
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        return content or "(caption unavailable)"
    except Exception as e:
        logger.warning(
            f"Qwen HTTP caption response parsing failed: status={resp.status_code} latency_ms={latency_ms} error={e}"
        )
        return "(caption unavailable)"


def classify_image(image_path: str, confidence_threshold: float = 0.25) -> List[Dict[str, Any]]:
    """
    Return a single caption entry using Qwen 2.5‑VL over HTTP.

    Args:
        image_path: Path to image file on disk.
        confidence_threshold: Ignored (kept for signature compatibility).

    Returns:
        List with one dict: {"label": <caption>, "category": "caption", "confidence": 1.0 or 0.0}
    """
    try:
        data_url = _encode_image_to_data_url(image_path)
        payload = _build_payload(data_url)
        caption = _post_chat_completions(payload)
        conf = 0.0 if caption == "(caption unavailable)" else 1.0
        return [{"label": caption, "category": "caption", "confidence": conf}]
    except Exception as e:
        logger.warning(f"Qwen HTTP caption pipeline failed for {image_path}: {e}")
        return [{"label": "(caption unavailable)", "category": "caption", "confidence": 0.0}]
