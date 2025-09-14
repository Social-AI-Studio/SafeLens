"""
LLM-driven suspicion scoring and planning module for PR4.2.

This module provides LLM-assisted pre-analysis capabilities that improve
evidence sampling density inside already-computed segments based on
suspicion scores and optional planning points.
"""

import os
import json
import time
import hashlib
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from ...tools.llm import SafetyLLM

logger = logging.getLogger(__name__)

# Simple in-memory cache for development (could be enhanced to use disk cache)
_cache = {}
_cache_timestamps = {}


@dataclass
class LLMPlannerConfig:
    """Configuration for LLM-driven suspicion scoring and planning."""
    
    # Planning mode
    planning_mode: str = "segmentation"  # segmentation|llm|hybrid
    
    # Suspicion selector
    suspicion_mode: str = "keywords"  # keywords|llm|off
    suspicion_llm_model: Optional[str] = None  # defaults to ANALYSIS_LLM_MODEL
    suspicion_llm_timeout_sec: float = 8.0
    suspicion_llm_conf_threshold: float = 0.6  # >= is suspicious
    suspicion_llm_max_segments: int = 50  # max segments scored per video
    suspicion_llm_min_text_chars: int = 80  # skip tiny slices
    suspicion_llm_cache_ttl_sec: int = 86400  # 24 hours
    
    # Note: Sampling cadence (seg_safe_sample_sec, seg_sus_sample_sec, max_frames_per_seg)
    # is handled by SegmentationConfig to avoid config drift
    
    # Planner (optional extra probe points)
    planner_llm_max_points: int = 5  # total extra timestamps per video
    planner_min_gap_sec: float = 8.0  # min spacing between probes
    planner_max_extra_frames: int = 120  # budget for frames from planned probes
    
    @classmethod
    def from_env(cls) -> "LLMPlannerConfig":
        """Create config from environment variables with fallbacks to defaults."""
        return cls(
            # Planning mode
            planning_mode=os.getenv("ANALYSIS_PLANNING_MODE", cls.planning_mode),
            
            # Suspicion selector
            suspicion_mode=os.getenv("SUSPICION_MODE", cls.suspicion_mode),
            suspicion_llm_model=os.getenv("SUSPICION_LLM_MODEL"),  # None means use default
            suspicion_llm_timeout_sec=float(os.getenv("SUSPICION_LLM_TIMEOUT_SEC", cls.suspicion_llm_timeout_sec)),
            suspicion_llm_conf_threshold=float(os.getenv("SUSPICION_LLM_CONF_THRESHOLD", cls.suspicion_llm_conf_threshold)),
            suspicion_llm_max_segments=int(os.getenv("SUSPICION_LLM_MAX_SEGMENTS", cls.suspicion_llm_max_segments)),
            suspicion_llm_min_text_chars=int(os.getenv("SUSPICION_LLM_MIN_TEXT_CHARS", cls.suspicion_llm_min_text_chars)),
            suspicion_llm_cache_ttl_sec=int(os.getenv("SUSPICION_LLM_CACHE_TTL_SEC", cls.suspicion_llm_cache_ttl_sec)),
            
            # Note: Sampling cadence handled by SegmentationConfig
            
            # Planner
            planner_llm_max_points=int(os.getenv("PLANNER_LLM_MAX_POINTS", cls.planner_llm_max_points)),
            planner_min_gap_sec=float(os.getenv("PLANNER_MIN_GAP_SEC", cls.planner_min_gap_sec)),
            planner_max_extra_frames=int(os.getenv("PLANNER_MAX_EXTRA_FRAMES", cls.planner_max_extra_frames))
        )
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        # Planning mode
        if self.planning_mode not in ("segmentation", "llm", "hybrid"):
            raise ValueError("planning_mode must be 'segmentation', 'llm', or 'hybrid'")
        
        # Suspicion
        if self.suspicion_mode not in ("keywords", "llm", "off"):
            raise ValueError("suspicion_mode must be 'keywords', 'llm', or 'off'")
        if self.suspicion_llm_timeout_sec <= 0:
            raise ValueError("suspicion_llm_timeout_sec must be positive")
        if not 0 <= self.suspicion_llm_conf_threshold <= 1:
            raise ValueError("suspicion_llm_conf_threshold must be between 0 and 1")
        if self.suspicion_llm_max_segments < 0:
            raise ValueError("suspicion_llm_max_segments must be non-negative")
        if self.suspicion_llm_min_text_chars < 0:
            raise ValueError("suspicion_llm_min_text_chars must be non-negative")
        if self.suspicion_llm_cache_ttl_sec < 0:
            raise ValueError("suspicion_llm_cache_ttl_sec must be non-negative")
        
        # Note: Sampling validation handled by SegmentationConfig
        
        # Planner
        if self.planner_llm_max_points < 0:
            raise ValueError("planner_llm_max_points must be non-negative")
        if self.planner_min_gap_sec < 0:
            raise ValueError("planner_min_gap_sec must be non-negative")
        if self.planner_max_extra_frames < 0:
            raise ValueError("planner_max_extra_frames must be non-negative")


def cache_key(video_id: str, seg_index: int, text_hash: str, kind: str) -> str:
    """
    Generate cache key for suspicion or planning results.
    
    Args:
        video_id: Video UUID
        seg_index: Segment index
        text_hash: SHA1 hash of segment text
        kind: "suspicion" or "points"
        
    Returns:
        Cache key string
    """
    return f"{video_id}:{seg_index}:{text_hash}:{kind}"


def _get_cached_result(key: str, ttl_sec: int) -> Optional[Dict[str, Any]]:
    """Get cached result if valid and not expired."""
    if key not in _cache:
        return None
    
    if key not in _cache_timestamps:
        # Malformed cache, remove entry
        del _cache[key]
        return None
    
    # Check expiration
    cached_time = _cache_timestamps[key]
    if time.time() - cached_time > ttl_sec:
        # Expired, remove
        del _cache[key]
        del _cache_timestamps[key]
        return None
    
    return _cache[key]


def _set_cached_result(key: str, result: Dict[str, Any]) -> None:
    """Cache result with timestamp."""
    _cache[key] = result
    _cache_timestamps[key] = time.time()


def suspicion_score(text: str, cfg: LLMPlannerConfig, video_id: str = "", seg_index: int = 0, llm: Optional['SafetyLLM'] = None) -> Dict[str, Any]:
    """
    Score segment text for suspicion using LLM.
    
    Args:
        text: Segment transcript text
        cfg: LLMPlannerConfig instance
        video_id: Video ID for caching/logging
        seg_index: Segment index for caching/logging
        
    Returns:
        Dict with 'suspicious' (bool), 'confidence' (float 0-1), 'category' (str|None), 'reason' (str)
    """
    # Validate input
    if not text or len(text.strip()) < cfg.suspicion_llm_min_text_chars:
        return {
            "suspicious": False,
            "confidence": 0.0,
            "category": None,
            "reason": "Text too short for analysis"
        }
    
    # Generate cache key
    text_hash = hashlib.sha1(text.encode('utf-8')).hexdigest()[:10]
    key = cache_key(video_id, seg_index, text_hash, "suspicion")
    
    # Check cache
    cached = _get_cached_result(key, cfg.suspicion_llm_cache_ttl_sec)
    if cached is not None:
        logger.debug(f"Suspicion cache hit for segment {seg_index}")
        # Mark as cache hit to avoid counting against budget
        cached_result = dict(cached)
        cached_result["_cache_hit"] = True
        return cached_result
    
    # Build LLM prompt
    prompt = f"""Analyze this video segment transcript for harmful content and respond with valid JSON only.

TRANSCRIPT:
{text.strip()}

Classify whether the excerpt likely contains or refers to harmful content (hate speech, violence, self-harm, nudity, drugs, abuse, harassment, misinformation).

Respond with JSON in exactly this format:
{{
  "suspicious": true/false,
  "confidence": 0.85,
  "category": "hate_speech"|null,
  "reason": "brief explanation"
}}

Categories can be: hate_speech, violence, nudity, self_harm, drugs, abuse, harassment, misinformation, or null.
Confidence should be 0.0 to 1.0. Only mark as suspicious if you have reasonable evidence."""
    
    try:
        # Use provided per-video LLM if available
        if llm is not None:
            backend = getattr(llm, "backend", "unknown")
            model_name = getattr(llm, "model", None)
            logger.debug(
                f"Using per-video LLM for suspicion scoring: backend={backend}, model={model_name}, video_id={video_id}, seg_index={seg_index}"
            )
            provided_llm = llm
        else:
            # Check for missing OpenRouter key when using openrouter backend
            if os.getenv('ANALYSIS_LLM_BACKEND', 'openrouter') == 'openrouter' and not os.getenv('OPENROUTER_API_KEY'):
                logger.warning(f"SUSPICION_MODE=llm requires OpenRouter; falling back to keywords. video_id={video_id}, seg_index={seg_index}")
                # Return keyword-based fallback (assumes keywords will be used by caller)
                return {
                    "suspicious": False,
                    "confidence": 0.0,
                    "category": None,
                    "reason": "OpenRouter key missing; using keyword fallback",
                    "_fallback": "openrouter_missing"
                }

            # Create LLM instance (use suspicion model if specified, else default)
            model = cfg.suspicion_llm_model  # None means use default from env
            provided_llm = SafetyLLM(model=model)
        
        # Set a short timeout for suspicion scoring
        start_time = time.time()
        result = provided_llm.invoke(prompt, max_tokens=150, temperature=0.3, timeout=int(cfg.suspicion_llm_timeout_sec))
        latency_ms = int((time.time() - start_time) * 1000)
        
        if isinstance(result, dict) and "error" not in result:
            # Validate and normalize result
            suspicious = bool(result.get('suspicious', False))
            confidence = float(result.get('confidence', 0.0))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0,1]
            
            category = result.get('category')
            if category and not isinstance(category, str):
                category = None
            
            reason = str(result.get('reason', ''))
            
            final_result = {
                "suspicious": suspicious,
                "confidence": confidence,
                "category": category,
                "reason": reason,
                "_latency_ms": latency_ms,
                "_cache_hit": False
            }
            
            # Cache the result (without the _cache_hit flag)
            cache_result = dict(final_result)
            cache_result.pop("_cache_hit", None)  # Remove cache flag before caching
            _set_cached_result(key, cache_result)
            
            logger.debug(f"LLM suspicion for segment {seg_index}: suspicious={suspicious}, confidence={confidence:.2f}, latency={latency_ms}ms")
            return final_result
        else:
            # LLM error - return safe default
            error_msg = result.get('error', 'Unknown LLM error') if isinstance(result, dict) else str(result)
            logger.warning(f"LLM suspicion error for segment {seg_index}: {error_msg}")
            
            fallback_result = {
                "suspicious": False,
                "confidence": 0.0,
                "category": None,
                "reason": f"LLM error: {error_msg}",
                "_error": True
            }
            return fallback_result
            
    except Exception as e:
        logger.error(f"LLM suspicion failed for segment {seg_index}: {e}")
        return {
            "suspicious": False,
            "confidence": 0.0,
            "category": None,
            "reason": f"Analysis failed: {str(e)}",
            "_error": True
        }


def propose_points(segment_text: str, seg_start: float, seg_end: float,
                   cfg: LLMPlannerConfig, video_id: str = "", seg_index: int = 0, llm: Optional['SafetyLLM'] = None) -> List[float]:
    """
    Propose additional probe timestamps within a segment using LLM.
    
    Args:
        segment_text: Transcript text for the segment
        seg_start: Segment start time in seconds
        seg_end: Segment end time in seconds
        cfg: LLMPlannerConfig instance
        video_id: Video ID for caching/logging
        seg_index: Segment index for caching/logging
        
    Returns:
        List of absolute timestamps (seconds) within [seg_start, seg_end]
    """
    # Validate input
    if not segment_text or len(segment_text.strip()) < cfg.suspicion_llm_min_text_chars:
        logger.debug(f"Segment {seg_index} text too short for planning")
        return []
    
    segment_duration = seg_end - seg_start
    if segment_duration < cfg.planner_min_gap_sec:
        logger.debug(f"Segment {seg_index} too short for additional probes ({segment_duration:.1f}s)")
        return []
    
    # Generate cache key
    text_hash = hashlib.sha1(segment_text.encode('utf-8')).hexdigest()[:10]
    key = cache_key(video_id, seg_index, text_hash, "points")
    
    # Check cache
    cached = _get_cached_result(key, cfg.suspicion_llm_cache_ttl_sec)
    if cached is not None:
        logger.debug(f"Planning cache hit for segment {seg_index}")
        # Add cache hit flag for potential metrics tracking
        cached["_cache_hit"] = True
        return cached.get("points", [])
    
    # Determine max points for this segment (proportional to duration, with minimum)
    max_points_for_segment = min(3, max(1, int(segment_duration / cfg.planner_min_gap_sec)))
    
    # Build LLM prompt
    prompt = f"""Analyze this video segment and propose timestamps where additional visual analysis would be most helpful.

SEGMENT: {seg_start:.1f}s to {seg_end:.1f}s (duration: {segment_duration:.1f}s)

TRANSCRIPT:
{segment_text.strip()}

Propose up to {max_points_for_segment} timestamps (in seconds relative to segment start) where visual evidence would clarify potentially harmful content. Focus on moments that might contain visual elements not captured in audio.

Respond with JSON in exactly this format:
{{
  "points": [2.5, 8.1, 12.3],
  "reason": "brief explanation"
}}

Points should be:
- Between 0.0 and {segment_duration:.1f} (relative to segment start)
- At least {cfg.planner_min_gap_sec:.1f}s apart
- Focused on potentially suspicious moments"""
    
    try:
        # Use provided per-video LLM if available
        if llm is not None:
            backend = getattr(llm, "backend", "unknown")
            model_name = getattr(llm, "model", None)
            logger.debug(
                f"Using per-video LLM for planning: backend={backend}, model={model_name}, video_id={video_id}, seg_index={seg_index}"
            )
            provided_llm = llm
        else:
            # Check for missing OpenRouter key when using openrouter backend
            if os.getenv('ANALYSIS_LLM_BACKEND', 'openrouter') == 'openrouter' and not os.getenv('OPENROUTER_API_KEY'):
                logger.warning(f"SUSPICION_MODE=llm requires OpenRouter; falling back to empty points. video_id={video_id}, seg_index={seg_index}")
                return []

            # Create LLM instance (use same model as suspicion)
            model = cfg.suspicion_llm_model
            provided_llm = SafetyLLM(model=model)
        
        start_time = time.time()
        result = provided_llm.invoke(prompt, max_tokens=200, temperature=0.5, timeout=int(cfg.suspicion_llm_timeout_sec))
        latency_ms = int((time.time() - start_time) * 1000)
        
        if isinstance(result, dict) and "error" not in result:
            raw_points = result.get('points', [])
            reason = str(result.get('reason', ''))
            
            if not isinstance(raw_points, list):
                raw_points = []
            
            # Convert relative points to absolute timestamps and validate
            absolute_points = []
            for point in raw_points:
                try:
                    relative_point = float(point)
                    if 0 <= relative_point <= segment_duration:
                        absolute_point = seg_start + relative_point
                        absolute_points.append(absolute_point)
                except (ValueError, TypeError):
                    continue
            
            # Enforce minimum gap between points
            absolute_points.sort()
            filtered_points = []
            for point in absolute_points:
                if not filtered_points or (point - filtered_points[-1]) >= cfg.planner_min_gap_sec:
                    filtered_points.append(point)
            
            # Limit to max points
            filtered_points = filtered_points[:max_points_for_segment]
            
            cache_result = {
                "points": filtered_points,
                "reason": reason,
                "_latency_ms": latency_ms,
                "_cache_hit": False
            }
            
            # Cache the result
            _set_cached_result(key, cache_result)
            
            logger.debug(f"LLM planning for segment {seg_index}: {len(filtered_points)} points, latency={latency_ms}ms")
            return filtered_points
            
        else:
            error_msg = result.get('error', 'Unknown LLM error') if isinstance(result, dict) else str(result)
            logger.warning(f"LLM planning error for segment {seg_index}: {error_msg}")
            return []
            
    except Exception as e:
        logger.error(f"LLM planning failed for segment {seg_index}: {e}")
        return []


def merge_timestamps_with_planning(periodic_timestamps: List[float], 
                                   planned_timestamps: List[float],
                                   cfg: LLMPlannerConfig,
                                   max_frames_per_segment: int = None,
                                   remaining_points_budget: int = None) -> List[float]:
    """
    Merge periodic sampling timestamps with planned probe points.
    
    Args:
        periodic_timestamps: Regular sampling timestamps
        planned_timestamps: LLM-proposed timestamps
        cfg: Configuration for gap and budget enforcement
        max_frames_per_segment: Maximum frames allowed for this segment
        remaining_points_budget: Remaining planned points budget for the video
        
    Returns:
        Merged and filtered list of timestamps
    """
    # Combine all timestamps
    all_timestamps = set(periodic_timestamps + planned_timestamps)
    sorted_timestamps = sorted(all_timestamps)
    
    # Apply minimum gap filter
    filtered_timestamps = []
    for ts in sorted_timestamps:
        if not filtered_timestamps or (ts - filtered_timestamps[-1]) >= cfg.planner_min_gap_sec:
            filtered_timestamps.append(ts)
    
    # Count how many are "extra" (from planning)
    planned_set = set(planned_timestamps)
    periodic_set = set(periodic_timestamps)
    
    # Separate into periodic and extra timestamps, maintaining order
    final_timestamps = []
    extra_added = 0
    
    # Calculate direct budget limits
    max_extra_by_segment = max_frames_per_segment - len(periodic_timestamps) if max_frames_per_segment else float('inf')
    max_extra_by_points = remaining_points_budget if remaining_points_budget is not None else float('inf')
    max_extra_by_frames = cfg.planner_max_extra_frames  # Interpret as max extra timestamps per video
    
    max_extra = min(max_extra_by_segment, max_extra_by_points, max_extra_by_frames)
    
    for ts in filtered_timestamps:
        is_extra = ts in planned_set and ts not in periodic_set
        
        if is_extra:
            if extra_added < max_extra:
                final_timestamps.append(ts)
                extra_added += 1
            # else: skip this extra timestamp due to budget
        else:
            # Always include periodic timestamps
            final_timestamps.append(ts)
    
    return sorted(final_timestamps)


# Default configuration instance
DEFAULT_CONFIG = LLMPlannerConfig()
