import asyncio
import logging
from fastapi import BackgroundTasks
from ..database import SessionLocal, Video
from ..services.analysis_pipeline import analyze_video_task

logger = logging.getLogger(__name__)


def enqueue_analysis(background_tasks: BackgroundTasks, video_id: str) -> None:
    """
    Enqueue video analysis as a background task.

    Args:
        background_tasks: FastAPI background tasks handler
        video_id: ID of the video to analyze
    """
    def run_analysis():
        new_db = SessionLocal()
        try:
            fresh_video = new_db.query(Video).filter(Video.id == video_id).first()
            if fresh_video:
                asyncio.run(analyze_video_task(video_id, fresh_video.file_path, new_db))
        finally:
            new_db.close()

    background_tasks.add_task(run_analysis)
