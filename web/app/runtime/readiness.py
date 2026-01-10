import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "ready": False,
    "status": "starting",
    "details": {},
    "updated_at": time.time(),
}


def set_not_ready(status: str, details: Optional[Dict[str, Any]] = None) -> None:
    with _lock:
        _state["ready"] = False
        _state["status"] = status
        _state["details"] = details or {}
        _state["updated_at"] = time.time()
    logger.info(f"Readiness: ready=false status={status}")


def set_ready(status: str = "ok", details: Optional[Dict[str, Any]] = None) -> None:
    with _lock:
        _state["ready"] = True
        _state["status"] = status
        _state["details"] = details or {}
        _state["updated_at"] = time.time()
    logger.info(f"Readiness: ready=true status={status}")


def get_readiness() -> Dict[str, Any]:
    with _lock:
        return dict(_state)

