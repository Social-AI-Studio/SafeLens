import os
import logging
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from ..database import Video, AnalysisRun
from ..tools.llm import SafetyLLM
from ..app.orchestration.segmentation_config import SegmentationConfig
from ..app.planning.llm_planner import LLMPlannerConfig
from ..app.orchestration.segment_analyzer import analyze_segments
from ..app.runtime.metrics import metrics

from ..utils.memory import current_rss_mb, free_accelerator_cache
from .transcript import load_transcript
from .segmentation_service import (
    read_existing_segments,
    segments_from_transcript,
    process_segments_with_visual_boundaries,
    write_segments,
)
from .persistence import cleanup_events_for_run, insert_harmful_events
from .reporting import (
    build_report_v2_for_run,
    attach_prose_summary,
    validate_report_v2_or_raise,
    save_report_v2_to_disk,
    update_video_summary_fields,
)
from .failures import mark_failure

logger = logging.getLogger(__name__)


def get_true_video_duration_seconds(video_path: str) -> float:
    """Return the real video duration in seconds.

    Tries ffprobe if available, then falls back to OpenCV frame count / FPS.
    Returns 0.0 when duration cannot be determined.
    """
    import shutil
    import subprocess
    import cv2

    try:
        if shutil.which("ffprobe"):
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                val = res.stdout.strip()
                if val:
                    dur = float(val)
                    if dur > 0:
                        return dur
    except Exception:
        pass

    try:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        cap.release()
        if fps and frame_count:
            dur = frame_count / fps
            if dur > 0:
                return dur
    except Exception:
        pass

    return 0.0


async def analyze_video_task(video_id: str, video_path: str, db: Session) -> None:
    """Background task to analyze video with memory monitoring and run tracking"""
    start_memory = current_rss_mb()
    start_time = datetime.now()

    try:
        logger.info(
            f"Starting analysis for video {video_id} (Memory: {start_memory:.1f}MB)"
        )

        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} not found in database")
            return

        analysis_run = AnalysisRun(
            video_id=video_id,
            status="processing",
            stage="e2e",
            model_used=video.analysis_model or "SafeLens/llama-3-8b",
        )
        db.add(analysis_run)
        db.commit()
        db.refresh(analysis_run)

        logger.info(f"Created analysis run {analysis_run.id} for video {video_id}")

        video.analysis_status = "processing"
        db.commit()

        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size_mb = Path(video_path).stat().st_size / 1024 / 1024
        logger.info(f"Processing video: {file_size_mb:.1f}MB")

        selected_model = video.analysis_model or "SafeLens/llama-3-8b"
        logger.info(f"Using selected model for analysis: {selected_model}")

        # Environment gating for model backends
        try:
            if selected_model == "SafeLens/llama-3-8b":
                forced_backend = "http"
            else:
                forced_backend = "openrouter"

            if forced_backend == "openrouter" and not os.getenv("OPENROUTER_API_KEY"):
                error_msg = f"Analysis failed - OpenRouter key missing: video_id={video_id}, model={selected_model}, backend={forced_backend}. Remediation: Set OPENROUTER_API_KEY to use non-SafeLens models"
                logger.error(error_msg)
                mark_failure(
                    db,
                    video,
                    analysis_run,
                    Path(video_path).parent,
                    Exception(error_msg),
                    start_time,
                )
                return

            if forced_backend == "http" and not os.getenv("ANALYSIS_LLM_HTTP_URL"):
                error_msg = f"Analysis failed - HTTP URL missing: video_id={video_id}, model={selected_model}, backend={forced_backend}. Remediation: Set ANALYSIS_LLM_HTTP_URL to use SafeLens/llama-3-8b over HTTP"
                logger.error(error_msg)
                mark_failure(
                    db,
                    video,
                    analysis_run,
                    Path(video_path).parent,
                    Exception(error_msg),
                    start_time,
                )
                return

            model_llm = SafetyLLM(model=selected_model, backend=forced_backend)
            backend = getattr(model_llm, "backend", "unknown")
            if backend == "http":
                base_url = os.getenv("ANALYSIS_LLM_HTTP_URL", "")
                logger.info(
                    f"Created LLM for model: {selected_model} (backend=http, base_url={base_url})"
                )
            else:
                logger.info(
                    f"Created LLM for model: {selected_model} (backend={backend})"
                )
        except Exception as e:
            logger.warning(f"Failed to create LLM for model {selected_model}: {e}")
            logger.warning("Falling back to local LLM provider")
            # Fallback to local provider to preserve behavior without hard failing
            model_llm = SafetyLLM(model=selected_model, backend="local")

        video_dir = Path(video_path).parent
        segments_file = video_dir / "segments.json"
        transcript_file = video_dir / "transcript.json"

        if segments_file.exists():
            logger.info("Using segment-based analysis pipeline")

            analysis_run.stage = "segmentation"
            analysis_run.planning_mode = "segmentation"
            db.commit()

            # Read existing segments
            segments = read_existing_segments(segments_file)

            duration = get_true_video_duration_seconds(video_path)
            if not duration and segments:
                duration = max(seg["end"] for seg in segments)
            video.duration = int(duration) if duration else None
            db.commit()

            # Load transcript for analysis context
            full_text, word_timestamps = load_transcript(
                video_id, video_path, transcript_file, db
            )

            seg_config = SegmentationConfig.from_env()
            planner_config = LLMPlannerConfig.from_env()
            planning_mode = planner_config.planning_mode

            analysis_run.stage = "analysis"
            analysis_run.segments_count = len(segments)
            db.commit()

            logger.info(f"Analyzing {len(segments)} segments...")
            analysis_start = datetime.now()

            harmful_events, token_usage = await analyze_segments(
                video_id=video_id,
                video_path=video_path,
                segments=segments,
                cfg=seg_config,
                llm=model_llm,
                full_text=full_text,
                word_timestamps=word_timestamps,
                planning_mode=planning_mode,
            )

            analysis_end = datetime.now()
            analysis_latency_ms = int(
                (analysis_end - analysis_start).total_seconds() * 1000
            )

            analysis_run.frames_analyzed = sum(
                event.get("num_frames", 0) for event in harmful_events
            )
            analysis_run.latency_ms = analysis_latency_ms

            if token_usage:
                analysis_run.tokens_prompt = token_usage.get("prompt_tokens", 0)
                analysis_run.tokens_completion = token_usage.get("completion_tokens", 0)
                logger.info(
                    f"Updated AnalysisRun with token usage: {analysis_run.tokens_prompt} prompt + {analysis_run.tokens_completion} completion"
                )

            db.commit()

            # Clean up previous events and insert new ones
            cleanup_events_for_run(db, analysis_run.id)
            inserted = insert_harmful_events(
                db, analysis_run.id, video_id, planning_mode, harmful_events
            )

            # Build report
            v2_report = build_report_v2_for_run(
                video_id, harmful_events, selected_model, planning_mode, analysis_run.id
            )

            # Try to generate prose summary
            prose = attach_prose_summary(
                model_llm, video_id, harmful_events, duration, full_text
            )
            if prose:
                v2_report["harmful_events_summary"] = prose
            else:
                from ..app.orchestration.report_builder import build_v2_summary

                summary_block = build_v2_summary(
                    video_id, harmful_events, total_duration_sec=duration
                )
                if (
                    isinstance(summary_block, dict)
                    and "harmful_events_summary" in summary_block
                ):
                    v2_report["harmful_events_summary"] = summary_block[
                        "harmful_events_summary"
                    ]

            validate_report_v2_or_raise(v2_report)

            analysis_run.status = "completed"
            total_latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            analysis_run.latency_ms = total_latency_ms
            db.commit()

            import json

            video.safety_report = json.dumps(v2_report, indent=2, ensure_ascii=False)
            video.analysis_status = "completed"

            # Update video summary fields
            update_video_summary_fields(video, v2_report)

            db.commit()

            save_report_v2_to_disk(v2_report, video_id, str(video_dir))

            metrics.log_video_metrics(
                video_id=video_id,
                total_latency_ms=total_latency_ms,
                segments_count=len(segments),
                frames_analyzed=analysis_run.frames_analyzed or 0,
                harmful_events_count=len(harmful_events),
                planning_mode=planning_mode,
                model_used=selected_model,
            )

            logger.info(
                f"PR2 analysis completed: {len(harmful_events)} harmful events detected"
            )

        else:
            auto_segmentation_enabled = (
                os.getenv("SEGMENTATION_AUTO", "true").lower() == "true"
            )

            if auto_segmentation_enabled:
                logger.info(
                    "Auto-segmentation enabled - generating segments and using PR2 pipeline"
                )

                analysis_run.stage = "segmentation"
                analysis_run.planning_mode = "segmentation"
                db.commit()

                try:
                    # Load or generate transcript
                    full_text, word_timestamps = load_transcript(
                        video_id, video_path, transcript_file, db
                    )

                    # Generate transcript-based segments
                    transcript_segments = segments_from_transcript(
                        full_text, word_timestamps, None, video_path
                    )

                    # Process with visual boundaries
                    cfg = SegmentationConfig.from_env()
                    final_segments = process_segments_with_visual_boundaries(
                        video_path, transcript_segments, cfg
                    )

                    # Write segments to file
                    write_segments(segments_file, final_segments)

                    duration = get_true_video_duration_seconds(video_path)
                    if not duration and final_segments:
                        duration = max(seg["end"] for seg in final_segments)
                    video.duration = int(duration) if duration else None
                    db.commit()

                    seg_config = SegmentationConfig.from_env()
                    planner_config = LLMPlannerConfig.from_env()
                    planning_mode = planner_config.planning_mode

                    analysis_run.stage = "analysis"
                    analysis_run.segments_count = len(final_segments)
                    db.commit()

                    logger.info(
                        f"Analyzing {len(final_segments)} auto-generated segments..."
                    )
                    analysis_start = datetime.now()

                    harmful_events, token_usage = await analyze_segments(
                        video_id=video_id,
                        video_path=video_path,
                        segments=final_segments,
                        cfg=seg_config,
                        llm=model_llm,
                        full_text=full_text,
                        word_timestamps=word_timestamps,
                        planning_mode=planning_mode,
                    )

                    analysis_end = datetime.now()
                    analysis_latency_ms = int(
                        (analysis_end - analysis_start).total_seconds() * 1000
                    )

                    analysis_run.frames_analyzed = sum(
                        event.get("num_frames", 0) for event in harmful_events
                    )
                    analysis_run.latency_ms = analysis_latency_ms

                    if token_usage:
                        analysis_run.tokens_prompt = token_usage.get("prompt_tokens", 0)
                        analysis_run.tokens_completion = token_usage.get(
                            "completion_tokens", 0
                        )
                        logger.info(
                            f"Updated AnalysisRun with token usage: {analysis_run.tokens_prompt} prompt + {analysis_run.tokens_completion} completion"
                        )

                    db.commit()

                    # Clean up previous events and insert new ones
                    cleanup_events_for_run(db, analysis_run.id)
                    inserted = insert_harmful_events(
                        db, analysis_run.id, video_id, planning_mode, harmful_events
                    )

                    # Build report
                    v2_report = build_report_v2_for_run(
                        video_id,
                        harmful_events,
                        selected_model,
                        planning_mode,
                        analysis_run.id,
                    )

                    # Try to generate prose summary
                    prose = attach_prose_summary(
                        model_llm, video_id, harmful_events, duration, full_text
                    )
                    if prose:
                        v2_report["harmful_events_summary"] = prose
                    else:
                        from ..app.orchestration.report_builder import build_v2_summary

                        summary_block = build_v2_summary(
                            video_id, harmful_events, total_duration_sec=duration
                        )
                        if (
                            isinstance(summary_block, dict)
                            and "harmful_events_summary" in summary_block
                        ):
                            v2_report["harmful_events_summary"] = summary_block[
                                "harmful_events_summary"
                            ]

                    validate_report_v2_or_raise(v2_report)

                    analysis_run.status = "completed"
                    total_latency_ms = int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    )
                    analysis_run.latency_ms = total_latency_ms
                    db.commit()

                    import json

                    video.safety_report = json.dumps(
                        v2_report, indent=2, ensure_ascii=False
                    )
                    video.analysis_status = "completed"

                    # Update video summary fields
                    update_video_summary_fields(video, v2_report)

                    db.commit()

                    save_report_v2_to_disk(v2_report, video_id, str(video_dir))

                    metrics.log_video_metrics(
                        video_id=video_id,
                        total_latency_ms=total_latency_ms,
                        segments_count=len(final_segments),
                        frames_analyzed=analysis_run.frames_analyzed or 0,
                        harmful_events_count=len(harmful_events),
                        planning_mode=planning_mode,
                        model_used=selected_model,
                    )

                    logger.info(
                        f"Auto-segmentation analysis completed: {len(harmful_events)} harmful events detected"
                    )

                except Exception as e:
                    logger.error(f"Auto-segmentation failed: {e}")
                    mark_failure(db, video, analysis_run, video_dir, e, start_time)
                    return
            else:
                logger.error("Auto-segmentation disabled - analysis cannot proceed")
                error_msg = "Auto-segmentation disabled - analysis cannot proceed"
                mark_failure(
                    db, video, None, video_dir, Exception(error_msg), start_time
                )
                return

        free_accelerator_cache()

        end_memory = current_rss_mb()
        peak_memory = current_rss_mb()
        logger.info(
            f"Analysis completed for video {video_id} (Memory: {end_memory:.1f}MB, Peak: ~{peak_memory:.1f}MB)"
        )

    except Exception as e:
        logger.error(f"Error analyzing video {video_id}: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())

        video = db.query(Video).filter(Video.id == video_id).first()
        analysis_run_obj = locals().get("analysis_run")
        mark_failure(
            db, video, analysis_run_obj, Path(video_path).parent, e, start_time
        )
    finally:
        free_accelerator_cache()
