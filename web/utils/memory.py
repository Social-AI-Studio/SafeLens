import psutil
import gc
import torch


def current_rss_mb() -> float:
    """Get current RSS memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def free_accelerator_cache() -> None:
    """Free GPU memory cache and run garbage collection."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
