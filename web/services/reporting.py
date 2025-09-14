import json
import logging
from typing import Dict, Any, List, Optional
from ..app.orchestration.report_builder import (
    build_report_v2,
    save_report_v2,
    validate_report_v2,
    get_analysis_summary,
    build_v2_summary,
)
from ..database import Video

logger = logging.getLogger(__name__)


def generate_prose_summary(
    llm: Any,
    video_id: str,
    events: List[Dict[str, Any]],
    total_duration_sec: Optional[float] = None,
    transcript_snippet: Optional[str] = None,
) -> Optional[str]:
    """Use the configured LLM to craft a short, user-friendly summary.

    Falls back to None on provider errors; caller should provide a deterministic fallback.
    """
    try:
        total = len(events)
        cat_counts: Dict[str, int] = {}
        for ev in events or []:
            cats = (ev.get("analysis_data") or {}).get("categories") or []
            if isinstance(cats, list):
                for c in cats:
                    if isinstance(c, str):
                        cat_counts[c] = cat_counts.get(c, 0) + 1

        def conf_of(e: Dict[str, Any]) -> int:
            try:
                v = (e.get("analysis_data") or {}).get("confidence", 0)
                return int(v)
            except Exception:
                return 0

        top_incidents = sorted(events, key=conf_of, reverse=True)[:3]
        incident_lines = []
        for ev in top_incidents:
            ts = f"{ev.get('segment_start')}–{ev.get('segment_end')}"
            cats = (ev.get("analysis_data") or {}).get("categories") or []
            cats_txt = (
                ", ".join([c for c in cats if isinstance(c, str)])
                if cats
                else "unspecified"
            )
            expl = (ev.get("analysis_data") or {}).get("explanation") or ""
            # Keep each incident concise
            line = f"- {ts}: {cats_txt}. {expl[:140]}"
            incident_lines.append(line)

        dur_txt = (
            f"{total_duration_sec:.0f} seconds"
            if total_duration_sec
            else "unknown duration"
        )
        cats_desc = (
            ", ".join(f"{k} ({v})" for k, v in sorted(cat_counts.items()))
            if cat_counts
            else "none"
        )

        context = []
        context.append(f"video_id: {video_id}")
        context.append(f"duration: {dur_txt}")
        context.append(f"total_harmful_events: {total}")
        context.append(f"categories: {cats_desc}")
        if incident_lines:
            context.append("incidents:\n" + "\n".join(incident_lines))
        if transcript_snippet:
            context.append("transcript_excerpt:\n" + transcript_snippet[:600])

        prompt = (
            "You are a content safety summarizer for a video analysis UI.\n"
            "Write a concise, neutral, end-user friendly summary (2–4 sentences) that:\n"
            "- states whether harmful content was found and roughly how much,\n"
            "- mentions notable categories in plain language,\n"
            "- gives a high-level sense of where issues occur,\n"
            "- avoids graphic details and quotations,\n"
            "- stays under 450 characters.\n\n"
            'Return JSON only: {"summary_text": string}.\n\n'
            f"CONTEXT:\n{chr(10).join(context)}\n"
        )

        resp = llm.invoke(prompt, max_tokens=320, temperature=0.2)
        if isinstance(resp, dict):
            text = resp.get("summary_text") or resp.get("harmful_events_summary")
            if isinstance(text, str) and text.strip():
                return text.strip()
        return None
    except Exception:
        return None


def build_report_v2_for_run(video_id: str, events: List[Dict[str, Any]], model_used: str, planning_mode: str, analysis_run_id: int) -> Dict[str, Any]:
    """
    Build a v2 report for the analysis run.

    Args:
        video_id: Video ID
        events: List of harmful events
        model_used: Model used for analysis
        planning_mode: Planning mode
        analysis_run_id: Analysis run ID

    Returns:
        Report dictionary
    """
    return build_report_v2(
        video_id=video_id,
        events=events,
        model_used=model_used,
        planning_mode=planning_mode,
        legacy_path=None,
        analysis_run_id=analysis_run_id,
    )


def attach_prose_summary(llm: Any, video_id: str, harmful_events: List[Dict[str, Any]], duration: float, full_text: Optional[str]) -> Optional[str]:
    """
    Generate prose summary using the LLM.

    Args:
        llm: LLM instance
        video_id: Video ID
        harmful_events: List of harmful events
        duration: Video duration
        full_text: Full transcript text

    Returns:
        Generated prose summary or None on failure
    """
    try:
        transcript_excerpt = None
        if full_text:
            transcript_excerpt = full_text[:1200]
        prose = generate_prose_summary(
            llm, video_id, harmful_events, duration, transcript_excerpt
        )
        return prose
    except Exception as e:
        logger.warning(f"Summary generation failed for {video_id}: {e}")
        return None


def validate_report_v2_or_raise(report: Dict[str, Any]) -> None:
    """
    Validate v2 report and raise if invalid.

    Args:
        report: Report dictionary to validate

    Raises:
        ValueError: If report validation fails
    """
    if not validate_report_v2(report):
        raise ValueError("Generated v2 report failed validation")


def save_report_v2_to_disk(report: Dict[str, Any], video_id: str, video_dir: str) -> None:
    """
    Save v2 report to disk.

    Args:
        report: Report dictionary
        video_id: Video ID
        video_dir: Video directory path
    """
    save_report_v2(report, video_id, video_dir)


def update_video_summary_fields(video: Video, report: Dict[str, Any]) -> None:
    """
    Update video summary fields based on the report.

    Args:
        video: Video database object
        report: Generated report
    """
    try:
        summary_stats = get_analysis_summary(report)
        video.harmful_events_count = summary_stats.get("total_harmful_events", 0)
        video.safety_rating = (
            "Unsafe" if (video.harmful_events_count or 0) > 0 else "Safe"
        )
        avg_conf = int(round(summary_stats.get("average_confidence", 0)))
        video.overall_confidence_score = avg_conf
        prose_summary = report.get("harmful_events_summary")
        if isinstance(prose_summary, str) and prose_summary.strip():
            video.summary = prose_summary.strip()
        else:
            cat_breakdown = summary_stats.get("category_breakdown", {})
            top_cats = (
                ", ".join(sorted(cat_breakdown.keys()))
                if cat_breakdown
                else "none"
            )
            video.summary = f"{video.harmful_events_count} harmful events (avg {avg_conf}%) • categories: {top_cats}"
    except Exception as e:
        logger.warning(f"Failed to set video summary fields for {video.id}: {e}")
