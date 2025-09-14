"""
Segment-level analysis module for PR2 implementation.

This module analyzes video segments by sampling frames, gathering evidence from
multiple modalities (vision, OCR, audio), and making LLM-based harm decisions.
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager

from ...tools.frame_extraction import extract_frames
from ...tools.image_classifier import classify_image
from ...tools.ocr import run_ocr
from ...tools.llm import SafetyLLM
from ...tools.transcription import transcribe_whole_video
from .segmentation_config import SegmentationConfig
from ..planning.llm_planner import (
    LLMPlannerConfig, suspicion_score as llm_suspicion_score, 
    propose_points, merge_timestamps_with_planning
)
from ..runtime.gpu_guard import gpu_guard
from ..runtime.metrics import metrics

logger = logging.getLogger(__name__)


def _apply_text_hygiene(text_parts: List[str], max_chars: int = 1500) -> str:
    """
    Apply text hygiene: dedupe consecutive identical lines and cap total length.
    
    Args:
        text_parts: List of text parts to process
        max_chars: Maximum character limit
        
    Returns:
        Cleaned and capped text string
    """
    if not text_parts:
        return ""
    
    # Dedupe consecutive identical lines
    deduped_parts = []
    prev_content = None
    
    for part in text_parts:
        # Extract content after timestamp for comparison
        if '] ' in part:
            content = part.split('] ', 1)[1] if '] ' in part else part
        else:
            content = part
            
        if content != prev_content:
            deduped_parts.append(part)
            prev_content = content
    
    # Join and cap total length
    full_text = '; '.join(deduped_parts)
    
    if len(full_text) > max_chars:
        # Try to cut at sentence boundary
        truncated = full_text[:max_chars]
        last_period = truncated.rfind('.')
        last_semicolon = truncated.rfind(';')
        
        # Cut at the latest sentence/section boundary
        cut_point = max(last_period, last_semicolon)
        if cut_point > max_chars * 0.8:  # Only if we don't lose too much
            full_text = truncated[:cut_point + 1] + "..."
        else:
            full_text = truncated + "..."
    
    logger.debug(f"Text hygiene: {len(text_parts)} -> {len(deduped_parts)} parts, {len(full_text)} chars")
    return full_text


# Removed signal-based timeout context manager as it doesn't work in background threads
# Provider-level timeouts are used instead (ANALYSIS_LLM_TIMEOUT_SEC)


# Keywords for suspicion detection - minimal false positives
SUSPICION_KEYWORDS = {
    "hate": [
        "nazi", "hitler", "swastika", "kkk", "white power", "n-word", "jew", "kike",
        "spic", "chink", "towelhead", "raghead", "faggot", "tranny", "retard"
    ],
    "self_harm": [
        "suicide", "kill myself", "end it all", "razor", "cutting", "self-harm",
        "overdose", "pills", "jump off", "hang myself"
    ],
    "nudity": [
        "naked", "nude", "penis", "vagina", "boobs", "tits", "ass", "porn",
        "sex tape", "masturbat", "orgasm", "horny"
    ],
    "drugs": [
        "cocaine", "heroin", "meth", "crack", "weed", "marijuana", "molly",
        "ecstasy", "lsd", "acid", "shrooms", "xanax", "oxy", "fentanyl"
    ],
    "violence": [
        "kill", "murder", "shoot", "stab", "beat up", "fight", "blood",
        "weapon", "gun", "knife", "bomb", "explosive", "torture"
    ],
    "abuse": [
        "molest", "rape", "assault", "abuse", "victim", "predator",
        "kidnap", "traffick", "exploit", "coerce"
    ]
}


def score_suspicion(segment_text: str, mode: str = "keywords",
                   planner_cfg: Optional['LLMPlannerConfig'] = None,
                   video_id: str = "", seg_index: int = 0, llm: Optional[SafetyLLM] = None) -> Dict[str, Any]:
    """
    Score segment for suspicion based on transcript text.
    
    Args:
        segment_text: Transcript text for the segment
        mode: Scoring mode - "keywords", "llm", or "off"
        planner_cfg: LLMPlannerConfig for LLM scoring (required for mode="llm")
        video_id: Video ID for caching/logging
        seg_index: Segment index for caching/logging
        
    Returns:
        Dict with 'suspicious' (bool), 'confidence' (float), 'method' (str), and optional other fields
    """
    if mode == "off":
        return {
            "suspicious": False,
            "confidence": 0.0,
            "method": "off",
            "reason": "Suspicion scoring disabled"
        }
    
    if mode == "keywords":
        if not segment_text:
            return {
                "suspicious": False,
                "confidence": 0.0,
                "method": "keywords",
                "reason": "No text available"
            }
            
        text_lower = segment_text.lower()
        
        # Check for any suspicious keywords
        for category, keywords in SUSPICION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    logger.info(f"Suspicion detected in segment {seg_index}: '{keyword}' in category '{category}'")
                    return {
                        "suspicious": True,
                        "confidence": 0.8,  # High confidence for keyword matches
                        "method": "keywords",
                        "category": category,
                        "keyword": keyword,
                        "reason": f"Keyword '{keyword}' found in {category}"
                    }
        
        return {
            "suspicious": False,
            "confidence": 0.9,  # High confidence that it's safe
            "method": "keywords",
            "reason": "No suspicious keywords found"
        }
    
    elif mode == "llm":
        if planner_cfg is None:
            logger.warning("LLM suspicion mode requires planner_cfg, falling back to keywords")
            return score_suspicion(segment_text, "keywords", None, video_id, seg_index)
        
        try:
            # Use LLM suspicion scoring
            llm_result = llm_suspicion_score(segment_text, planner_cfg, video_id, seg_index, llm=llm)
            
            # Add method and process result
            llm_result["method"] = "llm"
            
            # Check if it was an error case
            if llm_result.get("_error"):
                logger.warning(f"LLM suspicion error for segment {seg_index}, falling back to keywords")
                return score_suspicion(segment_text, "keywords", None, video_id, seg_index)
            
            # Convert confidence to suspicion based on threshold
            threshold = planner_cfg.suspicion_llm_conf_threshold
            if llm_result["confidence"] >= threshold:
                llm_result["suspicious"] = True
            
            logger.debug(f"LLM suspicion for segment {seg_index}: {llm_result['suspicious']} (conf={llm_result['confidence']:.2f})")
            return llm_result
            
        except Exception as e:
            logger.error(f"LLM suspicion failed for segment {seg_index}: {e}, falling back to keywords")
            return score_suspicion(segment_text, "keywords", None, video_id, seg_index)
    
    else:
        logger.warning(f"Unknown suspicion mode '{mode}', defaulting to keywords")
        return score_suspicion(segment_text, "keywords", None, video_id, seg_index)


def sample_frames(video_path: str, start: float, end: float, interval_sec: float, cap: int, 
                  timestamps: Optional[List[float]] = None) -> List[Dict[str, Any]]:
    """
    Sample frames from a video segment.
    
    Args:
        video_path: Path to video file
        start: Segment start time in seconds
        end: Segment end time in seconds
        interval_sec: Sampling interval in seconds
        cap: Maximum number of frames to sample
        timestamps: Optional specific timestamps to sample (overrides interval_sec)
        
    Returns:
        List of frame info dicts with 'ts' (timestamp) and 'path' (file path)
    """
    # Use provided timestamps or generate periodic ones
    if timestamps is not None:
        # Filter timestamps to segment bounds and apply cap
        segment_timestamps = [ts for ts in timestamps if start <= ts <= end]
        segment_timestamps = segment_timestamps[:cap]
    else:
        # Generate periodic timestamps within the segment
        segment_timestamps = []
        current = start
        while current < end and len(segment_timestamps) < cap:
            segment_timestamps.append(current)
            current += interval_sec
    
    # Extract frames at these timestamps
    try:
        frame_paths = extract_frames(video_path, timestamps=segment_timestamps)
        
        # Build result list with timestamp info
        results = []
        for i, path in enumerate(frame_paths):
            if i < len(segment_timestamps):
                results.append({
                    'ts': segment_timestamps[i],
                    'path': path
                })
        
        logger.info(f"Sampled {len(results)} frames from segment [{start:.1f}s-{end:.1f}s]")
        return results
        
    except Exception as e:
        logger.error(f"Failed to sample frames from segment [{start:.1f}s-{end:.1f}s]: {e}")
        return []


async def gather_evidence(frame_infos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Gather evidence from sampled frames using vision and OCR.
    
    Args:
        frame_infos: List of frame info dicts from sample_frames()
        
    Returns:
        Dict with 'captions', 'ocr', 'num_frames' keys
    """
    captions_parts = []
    ocr_parts = []
    num_frames = len(frame_infos)
    
    # Use GPU guard for vision analysis when analyzing multiple frames
    async with gpu_guard(f"vision_analysis_{num_frames}_frames"):
        for frame_info in frame_infos:
            frame_path = frame_info['path']
            timestamp = frame_info['ts']
            
            # Vision analysis with metrics
            try:
                with metrics.measure_operation("frame_vision_analysis", 
                                             video_ts=timestamp, 
                                             frame_path=frame_path):
                    labels = classify_image(frame_path)  # List[Dict]
                
                if isinstance(labels, list):
                    # priority: summary > caption > top label
                    summary_item = next((x for x in labels if x.get('category') == 'summary'), None)
                    caption_item = next((x for x in labels if x.get('category') == 'caption'), None)
                    if summary_item:
                        captions_parts.append(f"[{timestamp:.1f}s] {summary_item['label']}")
                    elif caption_item:
                        captions_parts.append(f"[{timestamp:.1f}s] Caption: {caption_item['label']}")
                    elif labels:
                        captions_parts.append(f"[{timestamp:.1f}s] Classification: {labels[0].get('label', 'unknown')}")
            except Exception as e:
                logger.warning(f"Vision analysis failed for frame at {timestamp:.1f}s: {e}")
            
            # OCR analysis with metrics
            try:
                with metrics.measure_operation("frame_ocr_analysis", 
                                             video_ts=timestamp,
                                             frame_path=frame_path):
                    ocr_text = run_ocr(frame_path)
                
                if ocr_text and ocr_text.strip():
                    ocr_parts.append(f"[{timestamp:.1f}s] {ocr_text.strip()}")
            except Exception as e:
                logger.warning(f"OCR analysis failed for frame at {timestamp:.1f}s: {e}")
    
    # Apply text hygiene: dedupe and cap length
    captions_text = _apply_text_hygiene(captions_parts, max_chars=1500)
    ocr_text = _apply_text_hygiene(ocr_parts, max_chars=1500)
    
    return {
        'captions': captions_text,
        'ocr': ocr_text,
        'num_frames': num_frames
    }


def segment_transcript(full_text: str, word_timestamps: List[Tuple[str, float]], 
                      start: float, end: float) -> str:
    """
    Extract transcript text for a specific segment using word timestamps.
    
    Args:
        full_text: Complete transcript text
        word_timestamps: List of (word, timestamp) tuples
        start: Segment start time
        end: Segment end time
        
    Returns:
        Transcript text for the segment, trimmed to reasonable length
    """
    if not word_timestamps:
        # Fallback: use proportional text based on time
        if not full_text:
            logger.info(f"No transcript available for segment [{start:.1f}s-{end:.1f}s]")
            return ""
        
        # This is a rough approximation - not ideal but better than nothing
        logger.info(f"Using approximate proportional slicing for segment [{start:.1f}s-{end:.1f}s] - word timestamps unavailable")
        duration_ratio = min(1.0, (end - start) / 300.0)  # Assume 5min max video
        text_len = len(full_text)
        start_char = int((start / 300.0) * text_len)
        end_char = int(start_char + (duration_ratio * text_len))
        
        segment_text = full_text[start_char:end_char]
    else:
        # Use word timestamps to extract precise segment
        logger.debug(f"Using word-level timestamps for precise segment extraction [{start:.1f}s-{end:.1f}s]")
        segment_words = []
        for word, timestamp in word_timestamps:
            if start <= timestamp <= end:
                segment_words.append(word)
        
        segment_text = ' '.join(segment_words)
        logger.debug(f"Extracted {len(segment_words)} words from segment")
    
    # Trim to reasonable length (500-1000 chars as per spec)
    if len(segment_text) > 1000:
        segment_text = segment_text[:1000] + "..."
    
    return segment_text


def transcribe_clip(video_path: str, start: float, end: float) -> str:
    """
    Transcribe a specific clip of video by extracting audio and using WhisperX.
    
    Args:
        video_path: Path to video file
        start: Clip start time
        end: Clip end time
        
    Returns:
        Transcript text for the clip, trimmed to ~1000 chars
    """
    try:
        # First check if we have cached full transcription
        video_dir = Path(video_path).parent
        transcript_file = video_dir / "transcript.json"
        
        if transcript_file.exists():
            with open(transcript_file, 'r') as f:
                transcript_data = json.load(f)
                full_text = transcript_data.get('full_text', '')
                word_timestamps = transcript_data.get('word_timestamps', [])
                return segment_transcript(full_text, word_timestamps, start, end)
        
        # If no cached transcript, extract and transcribe audio clip
        logger.info(f"Extracting and transcribing audio clip [{start:.1f}s-{end:.1f}s]")
        
        # Get ffmpeg binary path from environment
        ffmpeg_binary = os.getenv("FFMPEG_BINARY", "ffmpeg")
        
        # Create audio clips directory
        audio_clips_dir = video_dir / "audio_clips"
        audio_clips_dir.mkdir(exist_ok=True)
        
        # Generate clip filename
        start_ms = int(start * 1000)
        end_ms = int(end * 1000)
        clip_filename = f"clip_{start_ms}_{end_ms}.wav"
        clip_path = audio_clips_dir / clip_filename
        
        # Check if clip already exists
        if not clip_path.exists():
            # Extract audio clip using ffmpeg
            import subprocess
            cmd = [
                ffmpeg_binary,
                "-i", str(video_path),
                "-ss", str(start),
                "-t", str(end - start),
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # WAV format
                "-ar", "16000",  # 16kHz sample rate (good for speech recognition)
                "-ac", "1",  # Mono
                "-y",  # Overwrite if exists
                str(clip_path)
            ]
            
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=30,
                    check=True
                )
                logger.debug(f"FFmpeg extraction successful for clip [{start:.1f}s-{end:.1f}s]")
            except subprocess.TimeoutExpired:
                logger.error(f"FFmpeg timeout extracting clip [{start:.1f}s-{end:.1f}s]")
                return _fallback_transcript_extraction(video_path, start, end)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg failed extracting clip [{start:.1f}s-{end:.1f}s]: {e.stderr}")
                return _fallback_transcript_extraction(video_path, start, end)
            except FileNotFoundError:
                logger.error(f"FFmpeg binary not found: {ffmpeg_binary}")
                return _fallback_transcript_extraction(video_path, start, end)
        
        # Transcribe the audio clip with WhisperX
        if clip_path.exists() and clip_path.stat().st_size > 0:
            try:
                from ...tools.transcription import transcribe_whole_video
                
                # Use GPU guard and metrics for transcription
                with metrics.measure_operation("clip_transcription", 
                                             video_path=video_path, 
                                             start=start, 
                                             end=end,
                                             clip_duration=end-start):
                    
                    # Note: transcribe_whole_video can handle audio files too
                    clip_transcript = transcribe_whole_video(str(clip_path))
                
                if clip_transcript and 'full_text' in clip_transcript:
                    clip_text = clip_transcript['full_text']
                    
                    # Trim to reasonable length (~1000 chars)
                    if len(clip_text) > 1000:
                        clip_text = clip_text[:1000] + "..."
                    
                    logger.info(f"Successfully transcribed clip [{start:.1f}s-{end:.1f}s]: {len(clip_text)} chars")
                    return clip_text
                else:
                    logger.warning(f"WhisperX returned empty transcript for clip [{start:.1f}s-{end:.1f}s]")
                    return ""
                    
            except Exception as e:
                logger.error(f"WhisperX transcription failed for clip [{start:.1f}s-{end:.1f}s]: {e}")
                return _fallback_transcript_extraction(video_path, start, end)
        else:
            logger.error(f"Audio clip extraction failed - file not created or empty: {clip_path}")
            return _fallback_transcript_extraction(video_path, start, end)
        
    except Exception as e:
        logger.error(f"Failed to transcribe clip [{start:.1f}s-{end:.1f}s]: {e}")
        return _fallback_transcript_extraction(video_path, start, end)


def _fallback_transcript_extraction(video_path: str, start: float, end: float) -> str:
    """
    Fallback method for transcript extraction when ffmpeg or WhisperX fails.
    
    Args:
        video_path: Path to video file
        start: Clip start time 
        end: Clip end time
        
    Returns:
        Best-effort transcript text or empty string
    """
    try:
        # Try to use cached DB transcript if available
        logger.info(f"Using fallback transcript extraction for [{start:.1f}s-{end:.1f}s]")
        
        video_dir = Path(video_path).parent
        transcript_file = video_dir / "transcript.json"
        
        if transcript_file.exists():
            with open(transcript_file, 'r') as f:
                transcript_data = json.load(f)
                full_text = transcript_data.get('full_text', '')
                word_timestamps = transcript_data.get('word_timestamps', [])
                return segment_transcript(full_text, word_timestamps, start, end)
        
        # Last resort: return empty string
        logger.warning(f"No fallback transcript available for [{start:.1f}s-{end:.1f}s]")
        return ""
        
    except Exception as e:
        logger.error(f"Fallback transcript extraction failed for [{start:.1f}s-{end:.1f}s]: {e}")
        return ""


def llm_decide(audio_text: str, ocr_text: str, captions_text: str, llm: SafetyLLM, 
               timeout_sec: float = 30.0, segment_info: str = "unknown") -> Dict[str, Any]:
    """
    Use LLM to make harm decision based on multimodal evidence.
    
    Args:
        audio_text: Transcript text from segment
        ocr_text: OCR text from frames
        captions_text: Image captions/classifications from frames
        llm: SafetyLLM instance
        
    Returns:
        Dict with is_harmful, confidence, categories, explanation
    """
    # Normalize evidence with explicit placeholders (closer to qwenvl_gpt5_analysis prompt)
    audio_block = (audio_text or "").strip() or "No audio transcript available"
    ocr_block = (ocr_text or "").strip() or "No OCR text detected"
    captions_block = (captions_text or "").strip() or "No image descriptions available"

    prompt = f"""Analyze the following multimedia content from a video segment:

AUDIO TRANSCRIPT:
{audio_block}

OCR TEXT:
{ocr_block}

IMAGE DESCRIPTIONS:
{captions_block}

Determine if the content contains harmful, offensive, or inappropriate material. Consider:
- Religious/political/racial content is not automatically harmful
- Focus on whether it promotes harmful or discriminatory beliefs
- Evaluate context and potential implications

Respond with a JSON object containing:
- pred_is_harmful: boolean
- confidence: float between 0-1
- explanation: string (concise reasoning)
- harm_categories: list of strings (if any)

Only return valid JSON without any additional text."""
    
    try:
        # Call LLM with provider-level timeout (configured in SafetyLLM)
        result = llm.invoke(prompt)
        
        if isinstance(result, dict):
            # Check for provider-level error
            if "error" in result:
                logger.warning(f"LLM provider error for segment {segment_info}: {result['error']}")
                # Continue with fallback response below
            else:
                # Validate and normalize result
                is_harmful = bool(result.get('pred_is_harmful', False))
                confidence = float(result.get('confidence', 0.0))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0,1]
                
                categories = result.get('harm_categories', [])
                if not isinstance(categories, list):
                    categories = []
                
                explanation = str(result.get('explanation', '') or result.get('rationale', '') or result.get('reason', '') or result.get('justification', ''))
                
                logger.debug(f"LLM decision for segment {segment_info}: harmful={is_harmful}, confidence={confidence:.2f}")
                
                return {
                    'is_harmful': is_harmful,
                    'confidence': confidence,
                    'categories': categories,
                    'explanation': explanation,
                    '_token_usage': result.get('_token_usage')  # Preserve token usage if available
                }
        else:
            logger.error(f"LLM returned non-dict result for segment {segment_info}: {type(result)}")
            
    except Exception as e:
        logger.error(f"LLM decision failed for segment {segment_info}: {e}")
    
    # Fallback for any errors
    return {
        'is_harmful': False,
        'confidence': 0.0,
        'categories': [],
        'explanation': 'Analysis failed - assuming safe'
    }


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


async def analyze_segments(video_id: str, video_path: str, segments: List[Dict[str, float]], 
                          cfg: SegmentationConfig, llm: SafetyLLM,
                          full_text: str = None, word_timestamps: List[Tuple[str, float]] = None,
                          planning_mode: str = "segmentation") -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Analyze video segments and return harmful events.
    
    Args:
        video_id: Video UUID
        video_path: Path to video file
        segments: List of segment dicts with 'start' and 'end' keys
        cfg: Analysis configuration
        llm: SafetyLLM instance
        full_text: Optional full transcript text
        word_timestamps: Optional word-level timestamps
        planning_mode: Analysis planning mode (segmentation, llm, hybrid)
        
    Returns:
        Tuple of (harmful_events_list, aggregated_token_usage_dict)
    """
    logger.info(f"Analyzing {len(segments)} segments for video {video_id}")
    logger.info(f"Planning mode: {planning_mode}, Suspicion mode: {cfg.suspicion_mode}")
    logger.info(f"Safe sampling: {cfg.seg_safe_sample_sec}s, Suspicious sampling: {cfg.seg_suspicious_sample_sec}s")
    
    # Load LLM planner configuration
    planner_cfg = LLMPlannerConfig.from_env()
    planner_cfg.validate()
    # Log LLM budgets after config is initialized
    logger.info(
        f"LLM budgets: suspicion={planner_cfg.suspicion_llm_max_segments} segments, "
        f"planning={planner_cfg.planner_llm_max_points} points, "
        f"extra_frames={planner_cfg.planner_max_extra_frames}"
    )

    # Track budgets for LLM-based features
    suspicion_llm_calls = 0  # Track suspicion LLM calls per video
    planned_points_total = 0  # Track total planned points per video
    
    
    harmful_events = []
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0}
    
    for i, segment in enumerate(segments):
        start = segment['start']
        end = segment['end']
        segment_start_time = time.time()
        
        logger.info(f"Processing segment {i+1}/{len(segments)}: [{start:.1f}s-{end:.1f}s]")
        
        try:
            # 1. Get transcript for this segment
            if full_text is not None and word_timestamps is not None:
                segment_text = segment_transcript(full_text, word_timestamps, start, end)
            else:
                segment_text = transcribe_clip(video_path, start, end)
            
            # 2. Score suspicion with LLM planner integration (pre-check budget)
            current_suspicion_mode = cfg.suspicion_mode
            if (cfg.suspicion_mode == "llm" and 
                suspicion_llm_calls >= planner_cfg.suspicion_llm_max_segments):
                current_suspicion_mode = "keywords"  # Use keywords if budget exhausted
                logger.debug(f"Using keywords for segment {i} due to LLM budget ({suspicion_llm_calls}/{planner_cfg.suspicion_llm_max_segments})")
            
            suspicion_result = score_suspicion(
                segment_text,
                current_suspicion_mode,
                planner_cfg,
                video_id,
                i,
                llm=llm
            )
            
            # Handle LLM suspicion budget enforcement  
            if (cfg.suspicion_mode == "llm" and 
                suspicion_result.get("method") == "llm" and 
                not suspicion_result.get("_cache_hit", False)):
                suspicion_llm_calls += 1
            
            # Pre-check budget for future segments to avoid unnecessary LLM calls
            if (cfg.suspicion_mode == "llm" and 
                suspicion_llm_calls >= planner_cfg.suspicion_llm_max_segments):
                logger.info(f"LLM suspicion budget exhausted: used {suspicion_llm_calls}/{planner_cfg.suspicion_llm_max_segments}, switching to keywords for remaining segments")
                # Override suspicion mode for remaining segments
                cfg.suspicion_mode = "keywords"
            
            is_suspicious = suspicion_result["suspicious"]
            
            # 3. Planning step: propose additional probe points if enabled
            planned_timestamps = []
            if (planning_mode in ("llm", "hybrid") and 
                is_suspicious and 
                planned_points_total < planner_cfg.planner_llm_max_points):
                
                try:
                    with metrics.measure_operation("llm_planner", 
                                                 video_id=video_id,
                                                 segment_index=i,
                                                 segment_start=start,
                                                 segment_end=end):
                        proposed_points = propose_points(segment_text, start, end, planner_cfg, video_id, i, llm=llm)
                    
                    # Apply budget constraints
                    remaining_budget = planner_cfg.planner_llm_max_points - planned_points_total
                    planned_timestamps = proposed_points[:remaining_budget]
                    planned_points_total += len(planned_timestamps)
                    
                    if planned_timestamps:
                        logger.info(f"LLM planner proposed {len(planned_timestamps)} points for segment [{start:.1f}s-{end:.1f}s]")
                        
                except Exception as e:
                    logger.warning(f"LLM planner failed for segment [{start:.1f}s-{end:.1f}s]: {e}")
            
            # 4. Generate sampling timestamps (periodic + planned)
            interval = cfg.seg_suspicious_sample_sec if is_suspicious else cfg.seg_safe_sample_sec
            
            # Generate periodic timestamps
            periodic_timestamps = []
            current = start
            while current < end and len(periodic_timestamps) < cfg.max_frames_per_segment:
                periodic_timestamps.append(current)
                current += interval
            
            # Merge with planned timestamps if any
            if planned_timestamps:
                remaining_points_budget = planner_cfg.planner_llm_max_points - planned_points_total
                final_timestamps = merge_timestamps_with_planning(
                    periodic_timestamps, 
                    planned_timestamps, 
                    planner_cfg,
                    max_frames_per_segment=cfg.max_frames_per_segment,
                    remaining_points_budget=remaining_points_budget
                )
            else:
                final_timestamps = periodic_timestamps
            
            # 5. Sample frames using final timestamps
            frame_infos = sample_frames(video_path, start, end, interval, cfg.max_frames_per_segment, 
                                      timestamps=final_timestamps)
            
            if not frame_infos:
                logger.warning(f"No frames sampled for segment [{start:.1f}s-{end:.1f}s], skipping")
                continue
            
            # 6. Gather evidence from frames (async with GPU guard)
            evidence = await gather_evidence(frame_infos)
            
            # 7. LLM decision with metrics
            segment_info = f"[{start:.1f}s-{end:.1f}s]"
            
            with metrics.measure_operation("llm_decision", 
                                         video_id=video_id,
                                         segment_index=i,
                                         segment_start=start,
                                         segment_end=end):
                decision = llm_decide(
                    segment_text, 
                    evidence['ocr'], 
                    evidence['captions'], 
                    llm, 
                    timeout_sec=cfg.seg_llm_timeout_sec,
                    segment_info=segment_info
                )
            
            # 8. Create harmful event if LLM says it's harmful
            if decision['is_harmful']:
                # Determine which analysis types were performed
                analysis_performed = ["frame_extraction", "audio_analysis"]
                
                if evidence['captions']:
                    # Check if it looks like BLIP captions or CLIP classifications
                    if "Caption:" in evidence['captions']:
                        analysis_performed.append("image_captioning")
                    else:
                        analysis_performed.append("image_classification")
                
                if evidence['ocr']:
                    analysis_performed.append("ocr")
                
                harmful_event = {
                    "segment_start": format_timestamp(start),
                    "segment_end": format_timestamp(end),
                    "analysis_mode": "region",
                    "num_frames": evidence['num_frames'],
                    "analysis_performed": analysis_performed,
                    "audio_evidence": segment_text,
                    "analysis_data": {
                        "is_harmful": True,
                        "needs_verification": False,
                        "confidence": int(decision['confidence'] * 100),  # Scale to 0-100
                        "explanation": decision['explanation'],
                        "categories": decision['categories'],
                        "suspicion_method": suspicion_result.get("method", "unknown"),
                        "planning_mode": planning_mode,
                        "planned_points": len(planned_timestamps) if planned_timestamps else 0
                    }
                }
                
                
                harmful_events.append(harmful_event)
                logger.info(f"Harmful content detected in segment [{start:.1f}s-{end:.1f}s]: {decision['categories']}")
            else:
                logger.info(f"Segment [{start:.1f}s-{end:.1f}s] deemed safe")
            
            # Log segment metrics if enabled
            segment_end_time = time.time()
            segment_latency_ms = int((segment_end_time - segment_start_time) * 1000)
            
            # Extract token usage from decision if available
            tokens_used = decision.get("_token_usage")
            
            # Aggregate token usage for analysis run tracking
            if tokens_used:
                total_tokens["prompt_tokens"] += tokens_used.get("prompt_tokens", 0)
                total_tokens["completion_tokens"] += tokens_used.get("completion_tokens", 0)
            
            # Log LLM suspicion metrics if applicable
            if suspicion_result.get("method") == "llm" and not suspicion_result.get("_cache_hit", True):
                with metrics.measure_operation("llm_suspicion",
                                             video_id=video_id,
                                             segment_index=i,
                                             suspicious=suspicion_result["suspicious"],
                                             confidence=suspicion_result["confidence"],
                                             cache_hit=suspicion_result.get("_cache_hit", False),
                                             latency_ms=suspicion_result.get("_latency_ms", 0)):
                    pass  # The operation was already completed above
            
            # Enhanced segment metrics with planning info
            enhanced_decision = dict(decision)
            enhanced_decision.update({
                "suspicion_method": suspicion_result.get("method", "unknown"),
                "suspicion_confidence": suspicion_result.get("confidence", 0.0),
                "planning_mode": planning_mode,
                "planned_points": len(planned_timestamps) if planned_timestamps else 0,
                "total_timestamps": len(final_timestamps) if 'final_timestamps' in locals() else len([]),
            })
            
            metrics.log_segment_metrics(
                video_id=video_id,
                segment_index=i,
                segment_start=start,
                segment_end=end,
                latency_ms=segment_latency_ms,
                num_frames=evidence['num_frames'],
                suspicion_mode=cfg.suspicion_mode,
                is_suspicious=is_suspicious,
                decision=enhanced_decision,
                tokens_used=tokens_used
            )
                
        except Exception as e:
            logger.error(f"Failed to analyze segment [{start:.1f}s-{end:.1f}s]: {e}")
            continue
    
    logger.info(f"Analysis complete: {len(harmful_events)} harmful events detected out of {len(segments)} segments")
    logger.info(f"Budget usage: LLM suspicion {suspicion_llm_calls}/{planner_cfg.suspicion_llm_max_segments}, planned points {planned_points_total}/{planner_cfg.planner_llm_max_points}")
    logger.info(f"Token usage: {total_tokens['prompt_tokens']} prompt + {total_tokens['completion_tokens']} completion = {total_tokens['prompt_tokens'] + total_tokens['completion_tokens']} total")
    return harmful_events, total_tokens
