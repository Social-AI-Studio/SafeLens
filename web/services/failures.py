import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from ..database import Video, AnalysisRun
from ..utils.memory import current_rss_mb

logger = logging.getLogger(__name__)


def mark_failure(db: Session, video: Video, analysis_run: Optional[AnalysisRun], video_dir: Path, error: Exception, start_time: datetime) -> None:
    """
    Mark analysis as failed and write error log.

    Args:
        db: Database session
        video: Video object
        analysis_run: Analysis run object (may be None)
        video_dir: Video directory path
        error: Exception that caused failure
        start_time: Analysis start time
    """
    try:
        # Set video status
        video.analysis_status = "failed"
        db.commit()

        # Update analysis run if it exists
        try:
            if analysis_run:
                analysis_run.status = "failed"
                analysis_run.error = str(error)
                total_latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                analysis_run.latency_ms = total_latency_ms
                db.commit()
        except Exception as run_error:
            logger.error(f"Error updating analysis run: {str(run_error)}")

        # Write (append) error log
        error_path = video_dir / "error.log"
        with open(error_path, "a") as f:
            f.write(f"Error processing video: {str(error)}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}")
            f.write(f"Memory usage: {current_rss_mb():.1f}MB\n")

    except Exception as db_error:
        logger.error(f"Error updating database for failed analysis: {str(db_error)}")
