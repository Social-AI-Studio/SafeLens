import logging
from pathlib import Path
from fastapi import APIRouter
from ..app.health.providers import get_providers_health

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_FOLDER = Path("./videos")
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv", ".wmv"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "upload_folder": str(UPLOAD_FOLDER.absolute()),
        "allowed_extensions": list(ALLOWED_EXTENSIONS),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
    }


@router.get("/health/providers")
async def health_providers():
    """Provider readiness and configuration summary endpoint (PR3.5)"""
    try:
        health_data = await get_providers_health()
        return health_data
    except Exception as e:
        logger.error(f"Health providers check failed: {e}")
        return {"status": "error", "error": str(e), "providers": {}}
