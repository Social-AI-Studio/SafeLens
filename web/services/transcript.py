import json
import logging
from pathlib import Path
from typing import Tuple, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def load_transcript(video_id: str, video_path: str, transcript_file: Path, db: Session) -> Tuple[str, List[Tuple[str, float]]]:
    """
    Load transcript from file, database, or transcription service.

    Returns:
        Tuple of (full_text, word_timestamps) where word_timestamps is List[Tuple[str, float]]
        Never raises on missing data - returns empty strings/lists as fallback.
    """
    full_text = ""
    word_timestamps = []

    # Try loading from cached file first
    if transcript_file.exists():
        logger.info(f"Loading transcript from cached file: {transcript_file}")
        try:
            with open(transcript_file, "r") as f:
                transcript_data = json.load(f)
                full_text = transcript_data.get("full_text", "")
                word_timestamps = transcript_data.get("word_timestamps", [])
                # Convert list format to tuple format if needed
                if word_timestamps and isinstance(word_timestamps[0], list):
                    word_timestamps = [(w, t) for w, t in word_timestamps]
                return full_text, word_timestamps
        except Exception as e:
            logger.warning(f"Failed to read cached transcript for video {video_id}: {e}")

    # Try loading from database
    try:
        from ..database import Video
        video = db.query(Video).filter(Video.id == video_id).first()
        if video and video.transcription and video.transcription.full_text:
            logger.info(f"Loading transcript from database for video {video_id}")
            full_text = video.transcription.full_text
            try:
                word_timestamps = (
                    json.loads(video.transcription.word_timestamps)
                    if video.transcription.word_timestamps
                    else []
                )
                # Convert list format to tuple format if needed
                if word_timestamps and isinstance(word_timestamps[0], list):
                    word_timestamps = [(w, t) for w, t in word_timestamps]
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    f"Failed to parse word_timestamps from DB for video {video_id}"
                )
                word_timestamps = []

            # Cache to file for future use
            try:
                cache_data = {
                    "full_text": full_text,
                    "word_timestamps": word_timestamps,
                }
                with open(transcript_file, "w") as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"Cached transcript to file: {transcript_file}")
            except Exception as e:
                logger.warning(f"Failed to cache transcript to file: {e}")

            return full_text, word_timestamps
    except Exception as e:
        logger.warning(f"Failed to load transcript from database for video {video_id}: {e}")

    # Try transcribing if no existing transcript
    try:
        logger.info(f"Transcribing whole video: {video_path}")
        from ..tools.transcription import transcribe_whole_video

        transcript_result = transcribe_whole_video(video_path)
        if transcript_result and "full_text" in transcript_result:
            full_text = transcript_result["full_text"]
            word_timestamps = transcript_result.get("word_timestamps", [])

            # Cache to file
            cache_data = {
                "full_text": full_text,
                "word_timestamps": word_timestamps,
            }
            try:
                with open(transcript_file, "w") as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"Cached transcript to file: {transcript_file}")
            except Exception as e:
                logger.warning(f"Failed to cache transcript to file: {e}")

            # Store in database
            try:
                from ..database import Transcription, Video
                video = db.query(Video).filter(Video.id == video_id).first()
                if video:
                    transcript_row = (
                        db.query(Transcription)
                        .filter_by(video_id=video_id)
                        .first()
                    )

                    if transcript_row:
                        transcript_row.full_text = full_text
                        transcript_row.word_timestamps = json.dumps(word_timestamps)
                        logger.info(f"Updated existing transcription in DB for video {video_id}")
                    else:
                        transcript_row = Transcription(
                            video_id=video_id,
                            full_text=full_text,
                            word_timestamps=json.dumps(word_timestamps),
                        )
                        db.add(transcript_row)
                        logger.info(f"Created new transcription record in DB for video {video_id}")

                    db.commit()
            except Exception as e:
                logger.warning(f"Failed to store transcript in database: {e}")

            return full_text, word_timestamps
        else:
            logger.warning(f"Failed to transcribe video {video_id}")
    except Exception as e:
        logger.warning(f"Transcription failed for video {video_id}: {e}")

    # Fallback - return empty values (never raise)
    if not full_text and not word_timestamps:
        logger.warning(f"No transcript available for video {video_id} (neither file nor DB)")

    return full_text, word_timestamps
