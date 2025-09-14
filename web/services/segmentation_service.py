import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..app.orchestration.segmentation import process_segments, build_transcript_segments
from ..app.orchestration.segmentation_config import SegmentationConfig

logger = logging.getLogger(__name__)


def read_existing_segments(segments_file: Path) -> List[Dict[str, float]]:
    """
    Read and normalize segments from existing segments.json file.

    Args:
        segments_file: Path to segments.json file

    Returns:
        List of segment dictionaries with 'start' and 'end' keys
    """
    with open(segments_file, "r") as f:
        raw = json.load(f)

    segments = []
    if isinstance(raw, dict) and "segments" in raw:
        # shape: {"segments": [{"start":.., "end":..}, ...]}
        segments = raw["segments"]
    elif isinstance(raw, list):
        if raw and isinstance(raw[0], list) and len(raw[0]) == 2:
            # shape: [[start, end], ...]
            segments = [{"start": s, "end": e} for s, e in raw]
        elif (
            raw
            and isinstance(raw[0], dict)
            and "start" in raw[0]
            and "end" in raw[0]
        ):
            # shape: [{"start":.., "end":..}, ...]
            segments = raw

    # Normalize and filter valid segments
    segments = [
        s
        for s in segments
        if isinstance(s, dict)
        and "start" in s
        and "end" in s
        and s["end"] > s["start"]
    ]
    segments.sort(key=lambda s: (s["start"], s["end"]))

    logger.info(f"Loaded {len(segments)} segments from {segments_file}")
    return segments


def segments_from_transcript(full_text: str, word_timestamps: List[Tuple[str, float]], duration: Optional[float], video_path: str) -> List[Dict[str, float]]:
    """
    Generate segments from transcript using transcript segmentation logic.

    Args:
        full_text: Full transcript text
        word_timestamps: Word-level timestamps
        duration: Video duration in seconds
        video_path: Path to video file

    Returns:
        List of segment dictionaries
    """
    if full_text and word_timestamps:
        logger.info("Building transcript segments from full text and word timestamps")
        transcript_segments = build_transcript_segments(
            full_text=full_text, word_timestamps=word_timestamps
        )
    elif full_text:
        logger.info("Building transcript segments from full text only")
        transcript_segments = build_transcript_segments(full_text=full_text)
    else:
        logger.warning("No transcript available - creating time-based segments")
        from .analysis_pipeline import get_true_video_duration_seconds

        duration = duration or get_true_video_duration_seconds(video_path) or 60.0

        transcript_segments = []
        current_time = 0
        segment_duration = 10.0
        while current_time < duration:
            end_time = min(current_time + segment_duration, duration)
            transcript_segments.append({"start": current_time, "end": end_time})
            current_time = end_time

    logger.info(f"Created {len(transcript_segments)} transcript segments")
    return transcript_segments


def process_segments_with_visual_boundaries(video_path: str, transcript_segments: List[Dict[str, float]], cfg: SegmentationConfig) -> List[Dict[str, float]]:
    """
    Process segments with visual boundaries using the segmentation pipeline.

    Args:
        video_path: Path to video file
        transcript_segments: Initial transcript-based segments
        cfg: Segmentation configuration

    Returns:
        Final processed segments
    """
    logger.info("Processing segments with visual boundaries")
    final_segments = process_segments(video_path, transcript_segments, cfg)
    logger.info(f"Final segments after processing: {len(final_segments)}")
    return final_segments


def write_segments(segments_file: Path, segments: List[Dict[str, float]]) -> None:
    """
    Write segments to JSON file.

    Args:
        segments_file: Path to output segments.json file
        segments: List of segment dictionaries to write
    """
    segments_data = {"segments": segments}
    with open(segments_file, "w") as f:
        json.dump(segments_data, f, indent=2)
    logger.info(f"Saved segments to: {segments_file}")
