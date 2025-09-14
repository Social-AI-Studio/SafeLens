"""
Report builder module for generating v2 format analysis reports.

This module creates the final analysis report in v2 format with harmful events
and optional legacy report attachment for backward compatibility.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def build_report_v2(video_id: str, events: List[Dict[str, Any]], 
                   model_used: Optional[str] = None, 
                   planning_mode: Optional[str] = None,
                   legacy_path: Optional[str] = None,
                   analysis_run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Build a v2 format analysis report.
    
    Args:
        video_id: UUID of the analyzed video
        events: List of harmful event dicts from segment analysis
        model_used: Name of the LLM model used for analysis
        planning_mode: Analysis planning mode (e.g., "segmentation")
        legacy_path: Optional path to legacy safety_report.json for compatibility
        analysis_run_id: Optional analysis run ID for tracking
        
    Returns:
        Complete v2 format report dict
    """
    logger.info(f"Building v2 report for video {video_id} with {len(events)} harmful events")
    
    # Build the base v2 report structure
    report = {
        "format_version": 2,
        "video_id": video_id,
        "planning_mode": planning_mode or "segmentation",
        "harmful_events": events
    }
    
    # Add model info if available
    if model_used:
        report["model_used"] = model_used
    
    # Add analysis run ID if available (PR3.4)
    if analysis_run_id:
        report["analysis_run_id"] = analysis_run_id
    
    # Add legacy report for backward compatibility if it exists
    if legacy_path:
        try:
            legacy_file = Path(legacy_path)
            if legacy_file.exists():
                with open(legacy_file, 'r') as f:
                    legacy_data = json.load(f)
                    report["legacy_report"] = legacy_data
                    logger.info(f"Attached legacy report from {legacy_path}")
        except Exception as e:
            logger.warning(f"Failed to attach legacy report from {legacy_path}: {e}")
    
    logger.info(f"V2 report built successfully: {len(events)} harmful events, "
                f"format_version={report['format_version']}")
    
    return report


def save_report_v2(report: Dict[str, Any], video_id: str, video_dir: str) -> None:
    """
    Save v2 report to video directory.
    
    Args:
        report: V2 format report dict
        video_id: Video UUID
        video_dir: Path to video directory
        
    Returns:
        None
    """
    try:
        video_path = Path(video_dir)
        report_file = video_path / "safety_report.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"V2 report saved to {report_file}")
        
    except Exception as e:
        logger.error(f"Failed to save v2 report for video {video_id}: {e}")
        raise


def validate_report_v2(report: Dict[str, Any]) -> bool:
    """
    Validate that a report conforms to v2 format requirements.
    
    Args:
        report: Report dict to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check required top-level fields
        required_fields = ["format_version", "video_id", "planning_mode", "harmful_events"]
        for field in required_fields:
            if field not in report:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate format version
        if report["format_version"] != 2:
            logger.error(f"Invalid format_version: {report['format_version']}, expected 2")
            return False
        
        # Validate harmful_events structure
        events = report["harmful_events"]
        if not isinstance(events, list):
            logger.error("harmful_events must be a list")
            return False
        
        for i, event in enumerate(events):
            if not validate_harmful_event(event, i):
                return False
        
        logger.info(f"V2 report validation passed: {len(events)} events validated")
        return True
        
    except Exception as e:
        logger.error(f"Report validation failed with exception: {e}")
        return False


def validate_harmful_event(event: Dict[str, Any], index: int) -> bool:
    """
    Validate a single harmful event dict.
    
    Args:
        event: Harmful event dict to validate
        index: Event index for error reporting
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Required fields for harmful events
        required_fields = [
            "segment_start", "segment_end", "analysis_mode", 
            "num_frames", "analysis_performed", "audio_evidence", "analysis_data"
        ]
        
        for field in required_fields:
            if field not in event:
                logger.error(f"Event {index}: Missing required field '{field}'")
                return False
        
        # Validate specific field types and values
        if event["analysis_mode"] != "region":
            logger.error(f"Event {index}: analysis_mode must be 'region', got '{event['analysis_mode']}'")
            return False
        
        if not isinstance(event["num_frames"], int) or event["num_frames"] <= 0:
            logger.error(f"Event {index}: num_frames must be positive integer")
            return False
        
        if not isinstance(event["analysis_performed"], list):
            logger.error(f"Event {index}: analysis_performed must be a list")
            return False
        
        # Validate analysis_data structure
        analysis_data = event["analysis_data"]
        if not isinstance(analysis_data, dict):
            logger.error(f"Event {index}: analysis_data must be a dict")
            return False
        
        required_analysis_fields = [
            "is_harmful", "needs_verification", "confidence", "explanation", "categories"
        ]
        
        for field in required_analysis_fields:
            if field not in analysis_data:
                logger.error(f"Event {index}: Missing analysis_data field '{field}'")
                return False
        
        # Validate confidence range
        confidence = analysis_data["confidence"]
        if not isinstance(confidence, int) or not (0 <= confidence <= 100):
            logger.error(f"Event {index}: confidence must be integer 0-100, got {confidence}")
            return False
        
        # Validate categories
        if not isinstance(analysis_data["categories"], list):
            logger.error(f"Event {index}: categories must be a list")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Event {index} validation failed: {e}")
        return False


def get_analysis_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate summary statistics from v2 report.
    
    Args:
        report: V2 format report dict
        
    Returns:
        Summary dict with analysis statistics
    """
    events = report.get("harmful_events", [])
    
    # Count by category
    category_counts = {}
    total_events = len(events)
    
    for event in events:
        categories = event.get("analysis_data", {}).get("categories", [])
        for category in categories:
            category_counts[category] = category_counts.get(category, 0) + 1
    
    # Calculate confidence distribution
    confidences = [
        event.get("analysis_data", {}).get("confidence", 0) 
        for event in events
    ]
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Count analysis types used
    analysis_types = set()
    for event in events:
        types = event.get("analysis_performed", [])
        analysis_types.update(types)
    
    summary = {
        "total_harmful_events": total_events,
        "category_breakdown": category_counts,
        "average_confidence": round(avg_confidence, 1),
        "analysis_types_used": sorted(list(analysis_types)),
        "format_version": report.get("format_version"),
        "planning_mode": report.get("planning_mode")
    }
    
    return summary


def _coerce_event_confidence(events: List[Dict[str, Any]]) -> List[int]:
    vals: List[int] = []
    for e in events:
        try:
            conf = e.get("analysis_data", {}).get("confidence", 0)
            if isinstance(conf, (int, float)):
                vals.append(int(round(conf)))
        except Exception:
            continue
    return vals


def _category_counts(events: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for e in events:
        cats = e.get("analysis_data", {}).get("categories", []) or []
        if isinstance(cats, list):
            for c in cats:
                if not isinstance(c, str):
                    continue
                counts[c] = counts.get(c, 0) + 1
    return counts


def _pick_critical_incidents(events: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    def conf_of(e: Dict[str, Any]) -> int:
        try:
            v = e.get("analysis_data", {}).get("confidence", 0)
            return int(round(v))
        except Exception:
            return 0

    sorted_ev = sorted(events, key=conf_of, reverse=True)
    incidents: List[Dict[str, Any]] = []
    for ev in sorted_ev[:limit]:
        conf = conf_of(ev)
        sev = "High" if conf >= 80 else ("Medium" if conf >= 50 else "Low")
        cats = ev.get("analysis_data", {}).get("categories", []) or []
        if not isinstance(cats, list):
            cats = []
        incidents.append({
            "timestamp": ev.get("segment_start"),
            "severity": sev,
            "categories": cats,
            "visual_description": "Image/scene suggests: " + ("; ".join(cats) if cats else "potentially sensitive visuals"),
            "audio_description": ("Audio context present" if ev.get("audio_evidence") else "")
        })
    return incidents


def build_v2_summary(
    video_id: str,
    events: List[Dict[str, Any]],
    total_duration_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministic, low‑cost summary block for v2 reports.
    Returns a dict with keys similar to the legacy summary fields.
    """
    total = len(events)
    confs = _coerce_event_confidence(events)
    avg_conf = int(round(sum(confs) / len(confs))) if confs else 0
    cat_counts = _category_counts(events)
    top_cats = ", ".join(sorted(cat_counts.keys())) if cat_counts else "none"
    dur_txt = f"{total_duration_sec:.1f}-second video" if total_duration_sec else "video"

    harmful_events_summary = (
        f"{total} harmful event{'s' if total != 1 else ''} detected"
        + (f", including {top_cats}" if cat_counts else "")
        + (f", throughout the {dur_txt}." if total_duration_sec else ".")
    )

    # Very simple moderation heuristic
    high_risk = any(c.lower() in {"nudity", "sexuality", "violence"} for c in cat_counts.keys())
    moderation_recs = ["Remove content"] if high_risk and avg_conf >= 70 else ["Age restriction", "Review required"]

    incidents = _pick_critical_incidents(events, limit=3)
    detailed_evidence = (
        "Counts by category: " + ", ".join(f"{k}:{v}" for k, v in sorted(cat_counts.items()))
        if cat_counts else "No category breakdown available"
    )

    block = {
        "safety_rating": "Unsafe" if total > 0 else "Safe",
        "harmful_events_summary": harmful_events_summary,
        "critical_incidents": incidents,
        "moderation_recommendations": moderation_recs,
        "confidence_score": avg_conf,
        "detailed_evidence": detailed_evidence,
    }
    logger.info(f"Built deterministic v2 summary for video {video_id}: events={total}, avg_conf={avg_conf}")
    return block


def attach_v2_summary(report: Dict[str, Any], summary_block: Dict[str, Any]) -> Dict[str, Any]:
    """Attach a summary block to the base v2 report (non-destructive merge)."""
    if not isinstance(report, dict):
        return report
    try:
        report.update(summary_block or {})
    except Exception as e:
        logger.warning(f"Failed to attach v2 summary: {e}")
    return report
