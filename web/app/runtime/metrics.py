# app/runtime/metrics.py
"""
Observability metrics logging for analysis operations.

This module provides structured logging for performance metrics when
OBS_METRICS environment variable is enabled.
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Check if metrics are enabled
METRICS_ENABLED = os.getenv("OBS_METRICS", "false").lower() == "true"


class MetricsCollector:
    """Collects and logs structured metrics for analysis operations."""
    
    def __init__(self):
        self.enabled = METRICS_ENABLED
        if self.enabled:
            logger.info("Observability metrics enabled")
        else:
            logger.debug("Observability metrics disabled")
    
    def log_segment_metrics(self, 
                          video_id: str,
                          segment_index: int,
                          segment_start: float,
                          segment_end: float,
                          latency_ms: int,
                          num_frames: int,
                          suspicion_mode: str,
                          is_suspicious: bool,
                          decision: Dict[str, Any],
                          tokens_used: Optional[Dict[str, int]] = None) -> None:
        """
        Log structured metrics for a segment analysis.
        
        Args:
            video_id: Video UUID
            segment_index: Index of segment being analyzed
            segment_start: Segment start time in seconds
            segment_end: Segment end time in seconds  
            latency_ms: Analysis latency in milliseconds
            num_frames: Number of frames analyzed
            suspicion_mode: Suspicion scoring mode used
            is_suspicious: Whether segment was flagged as suspicious
            decision: LLM decision dict with is_harmful, confidence, etc.
            tokens_used: Optional token usage from LLM response
        """
        if not self.enabled:
            return
        
        # Build metrics payload
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "type": "segment_analysis",
            "video_id": video_id,
            "segment": {
                "index": segment_index,
                "start": segment_start,
                "end": segment_end,
                "duration": segment_end - segment_start,
                "suspicious": is_suspicious
            },
            "performance": {
                "latency_ms": latency_ms,
                "frames_analyzed": num_frames,
                "frames_per_second": num_frames / max(latency_ms / 1000.0, 0.001)
            },
            "analysis": {
                "suspicion_mode": suspicion_mode,
                "is_harmful": decision.get("is_harmful", False),
                "confidence": decision.get("confidence", 0.0),
                "categories": decision.get("categories", [])
            }
        }
        
        # Add token usage if available
        if tokens_used:
            metrics["tokens"] = tokens_used
        
        # Log structured metrics
        logger.info(f"METRICS: {json.dumps(metrics, separators=(',', ':'))}")
    
    def log_video_metrics(self,
                         video_id: str,
                         total_latency_ms: int,
                         segments_count: int,
                         frames_analyzed: int,
                         harmful_events_count: int,
                         planning_mode: str,
                         model_used: str) -> None:
        """
        Log structured metrics for complete video analysis.
        
        Args:
            video_id: Video UUID
            total_latency_ms: Total analysis latency
            segments_count: Number of segments processed
            frames_analyzed: Total frames analyzed
            harmful_events_count: Number of harmful events detected
            planning_mode: Analysis planning mode (segmentation/legacy)
            model_used: LLM model identifier
        """
        if not self.enabled:
            return
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "type": "video_analysis_complete",
            "video_id": video_id,
            "performance": {
                "total_latency_ms": total_latency_ms,
                "segments_processed": segments_count,
                "frames_analyzed": frames_analyzed,
                "harmful_events": harmful_events_count
            },
            "configuration": {
                "planning_mode": planning_mode,
                "model_used": model_used
            }
        }
        
        logger.info(f"METRICS: {json.dumps(metrics, separators=(',', ':'))}")
    
    @contextmanager
    def measure_operation(self, operation_name: str, **context):
        """
        Context manager to measure operation latency.
        
        Args:
            operation_name: Name of the operation being measured
            **context: Additional context to include in metrics
            
        Example:
            with metrics.measure_operation("clip_transcription", video_id="123", start=10.5, end=15.2):
                result = transcribe_clip(video_path, start, end)
        """
        if not self.enabled:
            yield
            return
        
        start_time = time.time()
        start_timestamp = datetime.now().isoformat()
        
        try:
            yield
            
            # Success metrics
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            metrics = {
                "log_timestamp": start_timestamp,
                "type": "operation_timing",
                "operation": operation_name,
                "latency_ms": latency_ms,
                "status": "success",
                **context
            }
            
            logger.info(f"METRICS: {json.dumps(metrics, separators=(',', ':'))}")
            
        except Exception as e:
            # Error metrics
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            metrics = {
                "log_timestamp": start_timestamp,
                "type": "operation_timing", 
                "operation": operation_name,
                "latency_ms": latency_ms,
                "status": "error",
                "error": str(e),
                **context
            }
            
            logger.info(f"METRICS: {json.dumps(metrics, separators=(',', ':'))}")
            raise


# Global metrics collector instance
metrics = MetricsCollector()