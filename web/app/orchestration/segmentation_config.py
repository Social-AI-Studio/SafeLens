"""
Segmentation configuration module with defaults and config struct.
"""
import os
from dataclasses import dataclass
from typing import Optional
import torch


@dataclass
class SegmentationConfig:
    """Configuration for video segmentation parameters."""
    
    # Segment duration constraints
    min_len_sec: float = 5.0
    max_len_sec: float = 16.0
    
    # Visual boundary detection
    scene_threshold: float = 0.85
    sample_interval_sec: float = 2.0
    batch_size: int = 8
    vit_model: str = "google/vit-base-patch16-224"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Transcript processing
    nltk_min_sentence_chars: int = 20
    
    # Iteration controls
    max_iterations: int = 7
    merge_threshold_factor: float = 1.2
    
    # Non-overlap normalization
    non_overlap_tolerance_sec: float = 0.20
    max_len_soft_factor: float = 1.15
    trim_to_transcript_boundaries: bool = True
    context_evidence_pad_sec: float = 1.5
    drop_tiny_after_trim_factor: float = 0.5
    
    # PR2: Segment analysis parameters
    seg_safe_sample_sec: float = 3.0
    seg_suspicious_sample_sec: float = 5.0
    max_frames_per_segment: int = 10
    suspicion_mode: str = "keywords"  # keywords|llm|off
    seg_llm_timeout_sec: float = 30.0
    
    @classmethod
    def from_env(cls) -> "SegmentationConfig":
        """Create config from environment variables with fallbacks to defaults."""
        return cls(
            min_len_sec=float(os.getenv("SEG_MIN_LEN_SEC", cls.min_len_sec)),
            max_len_sec=float(os.getenv("SEG_MAX_LEN_SEC", cls.max_len_sec)),
            scene_threshold=float(os.getenv("SEG_SCENE_THRESHOLD", cls.scene_threshold)),
            sample_interval_sec=float(os.getenv("SEG_SAMPLE_INTERVAL_SEC", cls.sample_interval_sec)),
            batch_size=int(os.getenv("SEG_BATCH_SIZE", cls.batch_size)),
            vit_model=os.getenv("SEG_VIT_MODEL", cls.vit_model),
            device=os.getenv("SEG_DEVICE", cls.device),
            nltk_min_sentence_chars=int(os.getenv("SEG_NLTK_MIN_SENTENCE_CHARS", cls.nltk_min_sentence_chars)),
            max_iterations=int(os.getenv("SEG_MAX_ITERATIONS", cls.max_iterations)),
            merge_threshold_factor=float(os.getenv("SEG_MERGE_THRESHOLD_FACTOR", cls.merge_threshold_factor)),
            non_overlap_tolerance_sec=float(os.getenv("SEG_NON_OVERLAP_TOLERANCE_SEC", cls.non_overlap_tolerance_sec)),
            max_len_soft_factor=float(os.getenv("SEG_MAX_LEN_SOFT_FACTOR", cls.max_len_soft_factor)),
            trim_to_transcript_boundaries=os.getenv("SEG_TRIM_TO_TRANSCRIPT_BOUNDARIES", str(cls.trim_to_transcript_boundaries)).lower() == "true",
            context_evidence_pad_sec=float(os.getenv("SEG_CONTEXT_EVIDENCE_PAD_SEC", cls.context_evidence_pad_sec)),
            drop_tiny_after_trim_factor=float(os.getenv("SEG_DROP_TINY_AFTER_TRIM_FACTOR", cls.drop_tiny_after_trim_factor)),
            # PR2: Segment analysis parameters
            seg_safe_sample_sec=float(os.getenv("SEG_SAFE_SAMPLE_SEC", cls.seg_safe_sample_sec)),
            seg_suspicious_sample_sec=float(os.getenv("SEG_SUS_SAMPLE_SEC", cls.seg_suspicious_sample_sec)),
            max_frames_per_segment=int(os.getenv("MAX_FRAMES_PER_SEG", cls.max_frames_per_segment)),
            suspicion_mode=os.getenv("SUSPICION_MODE", cls.suspicion_mode),
            seg_llm_timeout_sec=float(os.getenv("SEG_LLM_TIMEOUT_SEC", cls.seg_llm_timeout_sec))
        )
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.min_len_sec <= 0:
            raise ValueError("min_len_sec must be positive")
        if self.max_len_sec <= self.min_len_sec:
            raise ValueError("max_len_sec must be greater than min_len_sec")
        if not 0 < self.scene_threshold <= 1:
            raise ValueError("scene_threshold must be between 0 and 1")
        if self.sample_interval_sec <= 0:
            raise ValueError("sample_interval_sec must be positive")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.nltk_min_sentence_chars < 0:
            raise ValueError("nltk_min_sentence_chars must be non-negative")
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.merge_threshold_factor <= 1.0:
            raise ValueError("merge_threshold_factor must be greater than 1.0")
        if self.suspicion_mode not in ("keywords", "llm", "off"):
            raise ValueError("suspicion_mode must be 'keywords', 'llm', or 'off'")
        if self.seg_llm_timeout_sec <= 0:
            raise ValueError("seg_llm_timeout_sec must be positive")


# Default configuration instance
DEFAULT_CONFIG = SegmentationConfig()