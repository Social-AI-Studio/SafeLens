import json
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def cleanup_events_for_run(db: Session, analysis_run_id: int) -> None:
    """
    Delete AudioEvidence then HarmfulEvent for the analysis run.
    Commits the transaction and handles rollback on errors.
    """
    try:
        from ..database import HarmfulEvent, AudioEvidence

        # Delete AudioEvidence first (foreign key constraint)
        db.query(AudioEvidence).filter(
            AudioEvidence.harmful_event_id.in_(
                db.query(HarmfulEvent.id).filter(
                    HarmfulEvent.analysis_run_id == analysis_run_id
                )
            )
        ).delete(synchronize_session=False)

        # Then delete HarmfulEvent records
        db.query(HarmfulEvent).filter(
            HarmfulEvent.analysis_run_id == analysis_run_id
        ).delete(synchronize_session=False)

        db.commit()
    except Exception as e:
        logger.warning(f"Failed to cleanup previous events for run {analysis_run_id}: {e}")
        db.rollback()


def insert_harmful_events(db: Session, analysis_run_id: int, video_id: str, planning_mode: str, events: List[Dict[str, Any]]) -> int:
    """
    Insert HarmfulEvent and AudioEvidence records for the analysis run.

    Args:
        db: Database session
        analysis_run_id: ID of the analysis run
        video_id: Video ID
        planning_mode: Planning mode used
        events: List of event dictionaries with analysis data

    Returns:
        Number of events successfully inserted
    """
    from ..database import HarmfulEvent, AudioEvidence
    from ..utils.timecode import hhmmss_to_seconds

    inserted = 0
    for ev in events:
        try:
            start_s = hhmmss_to_seconds(ev.get("segment_start", "0"))
            end_s = hhmmss_to_seconds(ev.get("segment_end", "0"))
            data = ev.get("analysis_data", {})
            conf = int(data.get("confidence", 0))
            cats = data.get("categories", [])
            explanation = data.get("explanation", "")
            performed = ev.get("analysis_performed", [])

            row = HarmfulEvent(
                video_id=video_id,
                timestamp=start_s,
                start_time=start_s,
                end_time=end_s,
                confidence_score=conf,
                categories=json.dumps(cats, ensure_ascii=False),
                explanation=explanation,
                analysis_performed=json.dumps(performed, ensure_ascii=False),
                planning_mode=planning_mode,
                report_version=2,
                verification_source=None,
                severity=None,
                analysis_run_id=analysis_run_id,
            )
            db.add(row)
            db.flush()

            audio_text = ev.get("audio_evidence")
            if audio_text:
                db.add(
                    AudioEvidence(
                        harmful_event_id=row.id, transcript_snippet=audio_text
                    )
                )

            inserted += 1
        except Exception as ie:
            logger.warning(f"Skipping event due to insert error: {ie}")
            db.rollback()

    try:
        db.commit()
        logger.info(f"Persisted {inserted} harmful events for run {analysis_run_id}")
    except Exception as ce:
        logger.error(f"Failed to commit harmful events for run {analysis_run_id}: {ce}")
        db.rollback()

    return inserted
