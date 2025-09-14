# app/runtime/gpu_guard.py
"""
GPU resource management and concurrency guard.

This module provides a semaphore-based GPU resource guard to prevent
OOM errors when multiple heavy GPU operations run concurrently.
"""

import os
import asyncio
import logging
import threading
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Cross-loop/process-wide GPU semaphore (threading-based)
_gpu_semaphore: Optional[threading.Semaphore] = None
_gpu_lock = threading.Lock()
_gpu_active_count: int = 0
_gpu_max_concurrent: int = 0


def initialize_gpu_guard() -> None:
    """Initialize the global GPU guard semaphore based on environment configuration."""
    global _gpu_semaphore, _gpu_active_count, _gpu_max_concurrent

    max_concurrent = int(os.getenv("GPU_MAX_CONCURRENT", "1"))

    if max_concurrent <= 0:
        logger.info("GPU guard disabled (GPU_MAX_CONCURRENT=0)")
        _gpu_semaphore = None
        _gpu_active_count = 0
        _gpu_max_concurrent = 0
    else:
        logger.info(f"GPU guard initialized with max_concurrent={max_concurrent}")
        _gpu_semaphore = threading.Semaphore(max_concurrent)
        _gpu_active_count = 0
        _gpu_max_concurrent = max_concurrent


@asynccontextmanager
async def gpu_guard(operation_name: str = "GPU operation"):
    """
    Context manager for GPU resource protection.
    
    Args:
        operation_name: Name of the operation for logging
        
    Example:
        async with gpu_guard("BLIP-2 inference"):
            # GPU-intensive operation here
            result = model.generate(...)
    """
    global _gpu_semaphore, _gpu_active_count
    
    # Initialize if not already done
    if _gpu_semaphore is None and int(os.getenv("GPU_MAX_CONCURRENT", "1")) > 0:
        initialize_gpu_guard()
    
    # If guard is disabled or not configured, just yield
    if _gpu_semaphore is None:
        logger.debug(f"GPU guard bypass: {operation_name}")
        yield
        return

    # Acquire semaphore (cross-event-loop safe using threading.Semaphore)
    logger.debug(f"GPU guard acquire: {operation_name}")
    # Blocking acquire off the event loop thread to avoid blocking the loop
    await asyncio.to_thread(_gpu_semaphore.acquire)
    with _gpu_lock:
        _gpu_active_count += 1
    logger.debug(f"GPU guard acquired: {operation_name}")
    try:
        yield
    finally:
        with _gpu_lock:
            _gpu_active_count = max(0, _gpu_active_count - 1)
        _gpu_semaphore.release()
        logger.debug(f"GPU guard release: {operation_name}")


def get_gpu_guard_status() -> dict:
    """
    Get current GPU guard status for monitoring.
    
    Returns:
        Dict with guard status and configuration
    """
    global _gpu_semaphore, _gpu_active_count, _gpu_max_concurrent

    max_concurrent = int(os.getenv("GPU_MAX_CONCURRENT", "1"))

    if max_concurrent <= 0:
        return {
            "enabled": False,
            "max_concurrent": 0,
            "available": 0,
            "in_use": 0
        }

    if _gpu_semaphore is None:
        # Not initialized yet
        return {
            "enabled": True,
            "max_concurrent": max_concurrent,
            "available": max_concurrent,
            "in_use": 0,
            "status": "not_initialized"
        }

    # Calculate in-use slots based on our counter
    with _gpu_lock:
        in_use = int(_gpu_active_count)
    available = max(0, _gpu_max_concurrent - in_use)

    return {
        "enabled": True,
        "max_concurrent": _gpu_max_concurrent or max_concurrent,
        "available": available,
        "in_use": in_use
    }
