"""
Core segmentation module for partitioning videos into time segments.

Combines transcript sentence spans with visual scene-change detection
to create segments suitable for analysis.
"""
import logging
import math
import os
import re
from typing import Dict, List, Optional, Tuple, Any
import cv2
import torch
import numpy as np
from transformers import ViTImageProcessor, ViTModel
import nltk
from nltk.tokenize import sent_tokenize

from .segmentation_config import SegmentationConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

# Global model cache
_vit_cache = {}
_nltk_warned_missing = False


def _ensure_sentence_tokenizer() -> bool:
    """
    Ensure NLTK sentence tokenizer resources are available.

    In production we avoid downloading at runtime (set NLTK_AUTO_DOWNLOAD=false)
    and fall back to a lightweight regex-based sentence splitter when punkt is missing.
    """
    global _nltk_warned_missing

    # Try punkt_tab first (newer NLTK versions), then punkt.
    for resource in ("tokenizers/punkt_tab", "tokenizers/punkt"):
        try:
            nltk.data.find(resource)
            return True
        except LookupError:
            continue

    auto_download = os.getenv("NLTK_AUTO_DOWNLOAD", "false").lower() == "true"
    if not auto_download:
        if not _nltk_warned_missing:
            _nltk_warned_missing = True
            nltk_data = os.getenv("NLTK_DATA")
            logger.warning(
                "NLTK punkt data not found; falling back to naive sentence splitting. "
                "Remediation: mount/populate NLTK_DATA (e.g. /root/nltk_data) or set NLTK_AUTO_DOWNLOAD=true."
                + (f" (NLTK_DATA={nltk_data})" if nltk_data else "")
            )
        return False

    # Best-effort download (mainly for local dev).
    try:
        logger.info("Downloading NLTK punkt tokenizer data (NLTK_AUTO_DOWNLOAD=true)")
        try:
            nltk.download("punkt_tab", quiet=True)
        except Exception:
            pass
        try:
            nltk.download("punkt", quiet=True)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"NLTK download failed: {e}")
        return False

    for resource in ("tokenizers/punkt_tab", "tokenizers/punkt"):
        try:
            nltk.data.find(resource)
            return True
        except LookupError:
            continue
    return False


def _sent_tokenize_safe(text: str) -> List[str]:
    if not text:
        return []
    if _ensure_sentence_tokenizer():
        try:
            return [s for s in sent_tokenize(text) if isinstance(s, str) and s.strip()]
        except Exception:
            pass
    # Regex fallback: language-agnostic enough for our purposes.
    parts = re.split(r"(?<=[.!?])\\s+", text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def build_transcript_segments(
    whisper_segments: Optional[List[Dict]] = None,
    full_text: Optional[str] = None,
    word_timestamps: Optional[List[Tuple[str, float]]] = None,
    min_chars: int = 20
) -> List[Dict]:
    """
    Build transcript segments from various input formats.
    
    Args:
        whisper_segments: List of segments with start, end, text fields
        full_text: Full transcript text (used with word_timestamps)
        word_timestamps: List of (word, start_time) tuples
        min_chars: Minimum characters for a segment to be included
        
    Returns:
        List of segments with start, end, text fields, ordered and non-overlapping
    """
    logger.info("Building transcript segments")
    
    if whisper_segments:
        logger.info(f"Processing {len(whisper_segments)} Whisper segments")
        # Process whisper segments - split long segments into sentences if needed
        result_segments = []
        
        for seg in whisper_segments:
            text = seg.get('text', '').strip()
            if len(text) < min_chars:
                continue
                
            start = float(seg['start'])
            end = float(seg['end'])
            duration = end - start
            
            # If segment is reasonable length, keep as-is
            if len(text) <= 200 or duration <= 10.0:
                result_segments.append({
                    'start': start,
                    'end': end,
                    'text': text
                })
            else:
                # Split long segments into sentences
                sentences = _sent_tokenize_safe(text)
                if len(sentences) <= 1:
                    result_segments.append({
                        'start': start,
                        'end': end,
                        'text': text
                    })
                else:
                    # Distribute time evenly across sentences
                    time_per_char = duration / len(text) if len(text) > 0 else 0
                    current_time = start
                    
                    for sentence in sentences:
                        # Break if we've reached the end time
                        if current_time >= end:
                            break
                            
                        if len(sentence.strip()) >= min_chars:
                            sentence_duration = max(1.0, len(sentence) * time_per_char)
                            sentence_end = min(current_time + sentence_duration, end)
                            
                            # Only add if valid segment
                            if sentence_end > current_time:
                                result_segments.append({
                                    'start': current_time,
                                    'end': sentence_end,
                                    'text': sentence.strip()
                                })
                            current_time = sentence_end
        
        # Filter out any invalid segments (defensive)
        result_segments = [s for s in result_segments if s['end'] > s['start']]
        result_segments.sort(key=lambda x: x['start'])
        logger.info(f"Built {len(result_segments)} transcript segments from Whisper")
        return result_segments
        
    elif full_text and word_timestamps:
        logger.info(f"Processing full text with {len(word_timestamps)} word timestamps")
        # Sentence tokenization is best-effort; fall back if NLTK data is missing.

        def clean_token(token: str) -> str:
            return token.lower().strip('.,!?;:"()[]{}')

        # Tokenize into sentences
        sentences = _sent_tokenize_safe(full_text)
        result_segments = []

        cleaned_word_times = []
        raw_times = []
        for word, time in word_timestamps:
            try:
                timestamp = float(time)
            except (TypeError, ValueError):
                continue
            raw_times.append(timestamp)
            cleaned = clean_token(word)
            if cleaned:
                cleaned_word_times.append((cleaned, timestamp))

        if not raw_times:
            logger.warning("No usable word timestamps for alignment")
            return []

        overall_end = max(raw_times)
        pad_sec = 1.0

        sentence_infos = []
        for sentence in sentences:
            sentence_text = sentence.strip()
            if len(sentence_text) < min_chars:
                continue
            tokens_clean = [clean_token(token) for token in sentence_text.split()]
            tokens_clean = [token for token in tokens_clean if token]
            unit_count = len(tokens_clean) if tokens_clean else max(1, len(sentence_text))
            sentence_infos.append({
                'text': sentence_text,
                'tokens': tokens_clean,
                'units': unit_count,
            })

        total_units_remaining = sum(info['units'] for info in sentence_infos)
        wt_idx = 0
        last_end = 0.0

        for info in sentence_infos:
            while wt_idx < len(cleaned_word_times) and cleaned_word_times[wt_idx][1] < last_end:
                wt_idx += 1

            tokens = info['tokens']
            match_ratio = 0.0
            matched_indices: List[int] = []

            if tokens and cleaned_word_times:
                j = wt_idx
                for token in tokens:
                    while j < len(cleaned_word_times) and cleaned_word_times[j][0] != token:
                        j += 1
                    if j == len(cleaned_word_times):
                        break
                    matched_indices.append(j)
                    j += 1

                if tokens:
                    match_ratio = len(matched_indices) / len(tokens)

            if matched_indices and match_ratio >= 0.6:
                start_time = cleaned_word_times[matched_indices[0]][1]
                end_time = cleaned_word_times[matched_indices[-1]][1] + pad_sec
                wt_idx = matched_indices[-1] + 1
            else:
                if wt_idx < len(cleaned_word_times):
                    remaining_start = cleaned_word_times[wt_idx][1]
                    remaining_end = cleaned_word_times[-1][1]
                else:
                    remaining_start = last_end
                    remaining_end = overall_end

                remaining_start = max(remaining_start, last_end)
                remaining_end = max(remaining_end, remaining_start)
                remaining_duration = remaining_end - remaining_start

                proportion = info['units'] / total_units_remaining if total_units_remaining > 0 else 0.0
                fallback_duration = max(1.0, remaining_duration * proportion)
                start_time = remaining_start
                end_time = start_time + fallback_duration
                if remaining_end > start_time:
                    end_time = min(end_time, remaining_end + pad_sec)
                else:
                    end_time = start_time + pad_sec

            start_time = max(start_time, last_end)
            if end_time <= start_time:
                candidate_end = overall_end + pad_sec
                if candidate_end > start_time:
                    end_time = candidate_end
                else:
                    end_time = start_time + pad_sec

            if end_time > start_time:
                result_segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': info['text']
                })
                last_end = end_time

            total_units_remaining = max(0.0, total_units_remaining - info['units'])

        result_segments.sort(key=lambda x: x['start'])
        logger.info(f"Built {len(result_segments)} transcript segments from full text")
        return result_segments
    
    else:
        logger.warning("No valid transcript input provided")
        return []


def load_vit(model_name: str, device: str) -> Tuple[ViTImageProcessor, ViTModel]:
    """
    Load ViT model and processor with caching.
    
    Args:
        model_name: HuggingFace model name
        device: Device to load model on
        
    Returns:
        Tuple of (processor, model)
    """
    cache_key = f"{model_name}_{device}_fp16" if device.startswith("cuda") else f"{model_name}_{device}_fp32"
    
    if cache_key not in _vit_cache:
        logger.info(f"Loading ViT model {model_name} on {device}")
        try:
            processor = ViTImageProcessor.from_pretrained(model_name)
            model = ViTModel.from_pretrained(model_name)
            if device.startswith("cuda"):
                model = model.to(device).half()
            else:
                model = model.to(device)
            model.eval()
            _vit_cache[cache_key] = (processor, model)
            logger.info(f"Successfully loaded ViT model")
        except Exception as e:
            logger.error(f"Failed to load ViT model: {e}")
            raise
    
    return _vit_cache[cache_key]


def find_visual_boundaries(
    video_path: str,
    start: float,
    end: float,
    image_processor: ViTImageProcessor,
    vit_model: ViTModel,
    sampling_interval_sec: float = 2.0,
    batch_size: int = 8,
    threshold: float = 0.85,
    max_visual_frames: Optional[int] = None,
) -> List[float]:
    """
    Find visual scene boundaries using ViT embeddings.
    
    Args:
        video_path: Path to video file
        start: Start time in seconds
        end: End time in seconds
        image_processor: ViT image processor
        vit_model: ViT model
        sampling_interval_sec: Seconds between frame samples
        batch_size: Frames per batch
        threshold: Cosine similarity threshold for boundaries
        
    Returns:
        List of boundary timestamps within (start, end)
    """
    logger.info(f"Finding visual boundaries in [{start:.1f}, {end:.1f}]")
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Could not open video {video_path}")
            return []
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            logger.warning(f"Invalid FPS: {fps}")
            return []
            
        duration = max(0.0, end - start)
        effective_interval = sampling_interval_sec
        if max_visual_frames:
            adaptive_interval = duration / max_visual_frames if duration > 0 else sampling_interval_sec
            effective_interval = max(sampling_interval_sec, adaptive_interval)
            if effective_interval > sampling_interval_sec:
                logger.info(
                    f"Adaptive sampling interval {effective_interval:.2f}s for {duration:.1f}s span (cap {max_visual_frames})"
                )

        # Calculate sampling points
        sample_times = []
        current_time = start
        while current_time < end:
            sample_times.append(current_time)
            current_time += effective_interval

        if max_visual_frames and len(sample_times) > max_visual_frames:
            step = duration / max_visual_frames if max_visual_frames else sampling_interval_sec
            sample_times = [start + i * step for i in range(max_visual_frames)]
            sample_times = [t for t in sample_times if start <= t < end]
            logger.info(
                f"Capping visual sampling to {len(sample_times)} frames (interval ~{step:.2f}s)"
            )
            
        if len(sample_times) < 2:
            logger.info("Not enough samples for boundary detection")
            return []
            
        logger.info(f"Sampling {len(sample_times)} frames at ~{effective_interval:.2f}s intervals")
        
        # Extract frames
        frames = []
        valid_times = []
        
        for sample_time in sample_times:
            frame_number = int(sample_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if ret and frame is not None:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
                valid_times.append(sample_time)
            
        cap.release()
        
        if len(frames) < 2:
            logger.warning("Not enough valid frames extracted")
            return []
            
        logger.info(f"Extracted {len(frames)} valid frames")
        
        # Process frames in batches
        embeddings = []
        device = next(vit_model.parameters()).device
        
        with torch.no_grad():
            for i in range(0, len(frames), batch_size):
                batch_frames = frames[i:i + batch_size]
                
                # Preprocess batch
                inputs = image_processor(images=batch_frames, return_tensors="pt")
                target_dtype = next(vit_model.parameters()).dtype
                inputs = {k: v.to(device=device, dtype=target_dtype) for k, v in inputs.items()}
                
                # Get embeddings
                outputs = vit_model(**inputs)
                batch_embeddings = outputs.last_hidden_state.mean(dim=1)  # Pool over sequence
                embeddings.append(batch_embeddings.cpu())
        
        # Concatenate all embeddings
        all_embeddings = torch.cat(embeddings, dim=0)
        
        # Find boundaries based on cosine similarity
        boundaries = []
        
        for i in range(1, len(all_embeddings)):
            prev_emb = all_embeddings[i-1]
            curr_emb = all_embeddings[i]
            
            # Compute cosine similarity
            similarity = torch.cosine_similarity(prev_emb.unsqueeze(0), curr_emb.unsqueeze(0)).item()
            
            if similarity < threshold:
                boundary_time = valid_times[i]
                # Only include if strictly within (start, end)
                if start < boundary_time < end:
                    boundaries.append(boundary_time)
        
        boundaries.sort()
        logger.info(f"Found {len(boundaries)} visual boundaries")
        return boundaries
        
    except Exception as e:
        logger.error(f"Error in visual boundary detection: {e}")
        return []


def get_cached_visual_boundaries(
    start: float,
    end: float,
    visual_cache: Dict[Tuple[float, float], List[float]],
) -> Optional[List[float]]:
    cache_key = (round(start, 3), round(end, 3))
    if cache_key in visual_cache:
        logger.info(f"Using cached visual boundaries for span {cache_key}")
        return visual_cache[cache_key]

    reuse: Optional[List[float]] = None
    reuse_span: Optional[Tuple[float, float]] = None

    for (cached_start, cached_end), boundaries in visual_cache.items():
        if cached_start <= cache_key[0] and cached_end >= cache_key[1]:
            reuse = [b for b in boundaries if start < b < end]
            reuse_span = (cached_start, cached_end)
            break

    if reuse is not None:
        logger.info(
            f"Reusing cached visual boundaries from span {reuse_span} for {cache_key}"
        )
        visual_cache[cache_key] = reuse
        return reuse

    return None


def merge_spans(spans: List[Tuple[float, float]], epsilon: float = 1e-3) -> List[Tuple[float, float]]:
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda span: span[0])
    merged = [list(sorted_spans[0])]

    for start, end in sorted_spans[1:]:
        _, last_end = merged[-1]
        if start <= last_end + epsilon:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def split_long_segment(
    seg: Dict,
    video_path: str,
    transcript: List[Dict],
    image_processor: ViTImageProcessor,
    vit_model: ViTModel,
    cfg: SegmentationConfig,
    visual_cache: Optional[Dict[Tuple[float, float], List[float]]] = None,
) -> List[Dict]:
    """
    Split a segment that exceeds maximum length.
    
    Args:
        seg: Segment dictionary with start, end, text
        video_path: Path to video file
        transcript: List of transcript segments for reference
        image_processor: ViT image processor
        vit_model: ViT model
        cfg: Configuration object
        
    Returns:
        List of split segments
    """
    logger.info(f"Splitting long segment [{seg['start']:.1f}, {seg['end']:.1f}]")
    
    start = seg['start']
    end = seg['end']
    duration = end - start
    
    if duration <= cfg.max_len_sec:
        return [seg]
    
    # Find candidate boundaries
    candidates = []

    cache_key = (round(start, 3), round(end, 3))
    visual_boundaries: List[float]
    cached_boundaries = None
    if visual_cache is not None:
        cached_boundaries = get_cached_visual_boundaries(start, end, visual_cache)

    if cached_boundaries is not None:
        visual_boundaries = cached_boundaries
    else:
        visual_boundaries = find_visual_boundaries(
            video_path,
            start,
            end,
            image_processor,
            vit_model,
            cfg.sample_interval_sec,
            cfg.batch_size,
            cfg.scene_threshold,
            cfg.max_visual_frames,
        )
        if visual_cache is not None:
            visual_cache[cache_key] = visual_boundaries

    candidates.extend(visual_boundaries)
    
    # Add transcript segment boundaries that fall within this segment
    for t_seg in transcript:
        if start < t_seg['end'] < end:
            candidates.append(t_seg['end'])
    
    if not candidates:
        # No candidates found, use smart splitting
        return force_split_smart(seg, cfg)
    
    candidates = sorted(set(candidates))
    logger.info(f"Found {len(candidates)} candidate split points")
    
    # Try to create valid splits
    valid_splits = [start]
    
    for candidate in candidates:
        if candidate <= valid_splits[-1]:
            continue
            
        # Check if adding this candidate would create valid segments
        prev_end = valid_splits[-1]
        if candidate - prev_end >= cfg.min_len_sec:
            # Check if remainder would be valid
            remaining = end - candidate
            if remaining >= cfg.min_len_sec:
                valid_splits.append(candidate)
            elif remaining < cfg.min_len_sec and len(valid_splits) > 1:
                # Remove last split to merge remainder with previous segment
                valid_splits[-1] = candidate
    
    valid_splits.append(end)
    
    # Create segments
    result_segments = []
    for i in range(len(valid_splits) - 1):
        seg_start = valid_splits[i]
        seg_end = valid_splits[i + 1]
        
        if seg_end - seg_start >= cfg.min_len_sec:
            result_segments.append({
                'start': seg_start,
                'end': seg_end,
                'text': f"Split segment {i+1}"
            })
    
    if not result_segments:
        logger.warning("No valid splits found, using force split")
        return force_split_smart(seg, cfg)

    enforced_segments = []
    for result_seg in result_segments:
        seg_duration = result_seg['end'] - result_seg['start']
        if seg_duration > cfg.max_len_sec:
            enforced_segments.extend(force_split_smart(result_seg, cfg))
        else:
            enforced_segments.append(result_seg)

    logger.info(f"Split into {len(enforced_segments)} segments")
    return enforced_segments


def force_split_smart(seg: Dict, cfg: SegmentationConfig) -> List[Dict]:
    """
    Force split a segment using smart duration distribution.
    
    Args:
        seg: Segment to split
        cfg: Configuration object
        
    Returns:
        List of split segments
    """
    start = seg['start']
    end = seg['end']
    duration = end - start
    
    if duration <= cfg.max_len_sec:
        return [seg]
    
    # Calculate number of segments needed
    num_segments = math.ceil(duration / cfg.max_len_sec)
    segment_duration = duration / num_segments
    
    # Ensure minimum length constraint
    if segment_duration < cfg.min_len_sec:
        num_segments = max(1, math.floor(duration / cfg.min_len_sec))
        segment_duration = duration / num_segments
    
    result_segments = []
    current_start = start
    
    for i in range(num_segments):
        if i == num_segments - 1:
            # Last segment gets remaining time
            segment_end = end
        else:
            segment_end = current_start + segment_duration
        
        # Ensure minimum length for last segment
        if i == num_segments - 2 and (end - segment_end) < cfg.min_len_sec:
            # Merge last two segments
            segment_end = end
            result_segments.append({
                'start': current_start,
                'end': segment_end,
                'text': f"Force split segment {i+1}-{num_segments}"
            })
            break
        else:
            result_segments.append({
                'start': current_start,
                'end': segment_end,
                'text': f"Force split segment {i+1}"
            })
            current_start = segment_end
    
    logger.info(f"Force split into {len(result_segments)} segments")
    return result_segments


def merge_tiny_segments(
    segments: List[Dict],
    video_path: str,
    transcript: List[Dict],
    image_processor: ViTImageProcessor,
    vit_model: ViTModel,
    cfg: SegmentationConfig,
    visual_cache: Optional[Dict[Tuple[float, float], List[float]]] = None,
) -> List[Dict]:
    """
    Merge segments that are too short.
    
    Args:
        segments: List of segments to process
        video_path: Path to video file
        transcript: Transcript segments for reference
        image_processor: ViT image processor
        vit_model: ViT model
        cfg: Configuration object
        
    Returns:
        List of segments with tiny ones merged
    """
    if len(segments) <= 1:
        return segments
    
    logger.info(f"Merging tiny segments from {len(segments)} segments")
    
    result = []
    i = 0
    
    while i < len(segments):
        current_seg = segments[i]
        current_duration = current_seg['end'] - current_seg['start']
        
        if current_duration >= cfg.min_len_sec:
            result.append(current_seg)
            i += 1
            continue
        
        # Try to merge with next segment
        if i + 1 < len(segments):
            next_seg = segments[i + 1]
            merged_duration = next_seg['end'] - current_seg['start']
            
            if merged_duration <= cfg.max_len_sec * 1.5:  # Allow temporary over-merge
                merged_seg = {
                    'start': current_seg['start'],
                    'end': next_seg['end'],
                    'text': f"Merged: {current_seg.get('text', '')} + {next_seg.get('text', '')}"[:200]
                }
                
                # If merged segment is too long, split it again
                if merged_duration > cfg.max_len_sec:
                    split_segments = split_long_segment(
                        merged_seg, video_path, transcript, image_processor, vit_model, cfg, visual_cache
                    )
                    result.extend(split_segments)
                else:
                    result.append(merged_seg)
                
                i += 2  # Skip both segments
            else:
                # Can't merge, keep as-is
                result.append(current_seg)
                i += 1
        else:
            # Last segment, keep as-is
            result.append(current_seg)
            i += 1
    
    logger.info(f"Merged to {len(result)} segments")
    return result


def process_segments(
    video_path: str,
    transcript_segments: List[Dict],
    cfg: SegmentationConfig = DEFAULT_CONFIG
) -> List[Dict]:
    """
    Process transcript segments through iterative merge/split operations.
    
    Args:
        video_path: Path to video file
        transcript_segments: Initial transcript segments
        cfg: Configuration object
        
    Returns:
        List of processed segments with start/end times
    """
    logger.info(f"Processing {len(transcript_segments)} transcript segments")
    cfg.validate()
    
    if not transcript_segments:
        logger.warning("No transcript segments provided")
        return []
    
    # Per-run cache for visual boundaries to avoid recomputing on the same spans
    visual_cache: Dict[Tuple[float, float], List[float]] = {}

    vit_available = False
    # Load ViT model
    try:
        image_processor, vit_model = load_vit(cfg.vit_model, cfg.device)
        vit_available = True
    except Exception as e:
        logger.error(f"Failed to load ViT model: {e}")

    segments = transcript_segments.copy()
    
    # Sort segments by start time
    segments.sort(key=lambda x: x['start'])

    if vit_available:
        long_spans = [
            (seg['start'], seg['end'])
            for seg in segments
            if (seg['end'] - seg['start']) > cfg.max_len_sec
        ]
        if long_spans:
            merged_spans = merge_spans(long_spans)
            logger.info(
                f"Precomputing visual boundaries for {len(merged_spans)} merged spans "
                f"(from {len(long_spans)} long transcript spans)"
            )
            for span_start, span_end in merged_spans:
                cache_key = (round(span_start, 3), round(span_end, 3))
                if cache_key in visual_cache:
                    continue
                boundaries = find_visual_boundaries(
                    video_path,
                    span_start,
                    span_end,
                    image_processor,
                    vit_model,
                    cfg.sample_interval_sec,
                    cfg.batch_size,
                    cfg.scene_threshold,
                    cfg.max_visual_frames,
                )
                visual_cache[cache_key] = boundaries

    logger.info(f"Starting iterative processing with {len(segments)} segments")
    
    for iteration in range(cfg.max_iterations):
        logger.info(f"Iteration {iteration + 1}/{cfg.max_iterations}")
        initial_count = len(segments)
        
        # First, aggressively merge short segments
        merged_segments = []
        i = 0
        
        while i < len(segments):
            current = segments[i]
            current_duration = current['end'] - current['start']
            
            # Try to merge with next segment if current is short
            if (current_duration < cfg.min_len_sec and 
                i + 1 < len(segments)):
                next_seg = segments[i + 1]
                merged_duration = next_seg['end'] - current['start']
                
                # Allow temporary over-merge up to threshold factor
                if merged_duration <= cfg.max_len_sec * cfg.merge_threshold_factor:
                    merged = {
                        'start': current['start'],
                        'end': next_seg['end'],
                        'text': f"Merged: {current.get('text', '')} + {next_seg.get('text', '')}"[:200]
                    }
                    merged_segments.append(merged)
                    i += 2
                else:
                    merged_segments.append(current)
                    i += 1
            else:
                merged_segments.append(current)
                i += 1
        
        segments = merged_segments
        
        # Then split segments that exceed max length
        split_segments = []
        for seg in segments:
            duration = seg['end'] - seg['start']
            if duration > cfg.max_len_sec:
                if vit_available:
                    split_result = split_long_segment(
                        seg, video_path, transcript_segments, image_processor, vit_model, cfg, visual_cache
                    )
                else:
                    split_result = force_split_smart(seg, cfg)
                split_segments.extend(split_result)
            else:
                split_segments.append(seg)
        segments = split_segments
        
        segments.sort(key=lambda x: x['start'])
        
        logger.info(f"Iteration {iteration + 1} complete: {initial_count} → {len(segments)} segments")
        
        # Check convergence
        if len(segments) == initial_count:
            logger.info("Converged early")
            break
    
    # Final merge pass for tiny segments
    if vit_available:
        segments = merge_tiny_segments(
            segments, video_path, transcript_segments, image_processor, vit_model, cfg, visual_cache
        )
    
    # Final validation and cleanup
    final_segments = []
    for seg in segments:
        duration = seg['end'] - seg['start']
        if duration >= cfg.min_len_sec and duration <= cfg.max_len_sec:
            final_segments.append({
                'start': seg['start'],
                'end': seg['end']
            })
        elif duration > 0:
            # Keep segments that don't meet ideal constraints but are valid
            logger.warning(f"Segment [{seg['start']:.1f}, {seg['end']:.1f}] duration {duration:.1f}s outside ideal range")
            final_segments.append({
                'start': seg['start'],
                'end': seg['end']
            })
    
    final_segments.sort(key=lambda x: x['start'])
    logger.info(f"Final processing complete: {len(final_segments)} segments")
    
    # Construct transcript boundaries for normalization
    transcript_bounds = []
    for seg in transcript_segments:
        transcript_bounds.extend([seg['start'], seg['end']])
    transcript_bounds = sorted(list(set(transcript_bounds)))  # Deduplicate and sort
    
    # Apply non-overlap normalization
    normalized_segments = normalize_non_overlap(final_segments, transcript_bounds, cfg)

    if not vit_available:
        capped_segments = []
        for seg in normalized_segments:
            duration = seg['end'] - seg['start']
            if duration > cfg.max_len_sec:
                split_segments = force_split_smart(seg, cfg)
                capped_segments.extend(
                    [{'start': split_seg['start'], 'end': split_seg['end']} for split_seg in split_segments]
                )
            else:
                capped_segments.append(seg)
        normalized_segments = sorted(capped_segments, key=lambda x: x['start'])
    
    return normalized_segments


def normalize_non_overlap(
    segments: List[Dict], 
    transcript_bounds: List[float], 
    cfg: SegmentationConfig
) -> List[Dict]:
    """
    Normalize segments to ensure non-overlapping event windows.
    
    Args:
        segments: List of segments with start/end times
        transcript_bounds: All transcript segment boundaries (starts and ends)
        cfg: Configuration object
        
    Returns:
        List of normalized non-overlapping segments
    """
    if not segments:
        return []
    
    segs = sorted(segments, key=lambda s: (s['start'], s['end']))
    final = []
    last_end = None
    soft_max = cfg.max_len_sec * cfg.max_len_soft_factor
    tol = cfg.non_overlap_tolerance_sec
    drop_tiny_factor = cfg.drop_tiny_after_trim_factor

    def snap_up_to_transcript(t: float) -> float:
        """Snap time to nearest transcript boundary within tolerance."""
        if not cfg.trim_to_transcript_boundaries or not transcript_bounds:
            return t
        # Find smallest boundary >= t within tolerance
        candidates = [b for b in transcript_bounds if b >= t and (b - t) <= tol]
        return min(candidates) if candidates else t

    def snap_down_to_transcript(t: float) -> float:
        """Snap time down to nearest transcript boundary within tolerance."""
        if not cfg.trim_to_transcript_boundaries or not transcript_bounds:
            return t
        candidates = [b for b in transcript_bounds if b <= t and (t - b) <= tol]
        return max(candidates) if candidates else t

    logger.info(f"Normalizing {len(segs)} segments for non-overlap")
    
    for seg in segs:
        s, e = seg['start'], seg['end']
        if last_end is None:
            final.append({'start': s, 'end': e})
            last_end = e
            continue

        # Check for overlap
        if s < (last_end - tol):
            # Try to merge if under soft cap
            merged_len = max(final[-1]['end'], e) - final[-1]['start']
            if merged_len <= soft_max:
                final[-1]['end'] = max(final[-1]['end'], e)
                last_end = final[-1]['end']
                logger.debug(f"Merged overlapping segments: [{final[-1]['start']:.1f}, {final[-1]['end']:.1f}]")
                continue
            
            # Else trim current start
            new_start = snap_up_to_transcript(max(last_end, s))
            if (e - new_start) < (cfg.min_len_sec * drop_tiny_factor):
                prev = final[-1]
                boundary = max(prev['start'] + cfg.min_len_sec, e - cfg.min_len_sec)
                boundary = snap_down_to_transcript(boundary)

                if boundary > prev['start'] and boundary < e and (e - boundary) >= cfg.min_len_sec:
                    prev['end'] = boundary
                    last_end = prev['end']
                    s = boundary
                    logger.debug(
                        f"Reallocated overlap boundary: prev_end -> {boundary:.1f}"
                    )
                else:
                    merged_seg = {
                        'start': prev['start'],
                        'end': max(prev['end'], e)
                    }
                    split_segments = force_split_smart(merged_seg, cfg)
                    final.pop()
                    final.extend(
                        {'start': split_seg['start'], 'end': split_seg['end']}
                        for split_seg in split_segments
                    )
                    last_end = final[-1]['end'] if final else None
                    logger.debug(
                        f"Merged overlap into {len(split_segments)} segments to preserve coverage"
                    )
                    continue
            else:
                s = new_start
                logger.debug(f"Trimmed overlapping segment start: {seg['start']:.1f} -> {s:.1f}")

        # Soft max guard (large outliers should be split earlier)
        if (e - s) > soft_max:
            e = s + soft_max
            logger.debug(f"Clamped segment to soft max: end {seg['end']:.1f} -> {e:.1f}")

        final.append({'start': s, 'end': e})
        last_end = e

    # Final sweep: clamp any micro-overlaps
    out = []
    last_end = None
    for seg in final:
        s, e = seg['start'], seg['end']
        if last_end is not None and s < (last_end - tol):
            s = last_end
            logger.debug(f"Final clamp: adjusted start to {s:.1f}")
        if e <= s:
            logger.debug(f"Dropping invalid segment: [{s:.1f}, {e:.1f}]")
            continue
        out.append({'start': s, 'end': e})
        last_end = e

    logger.info(f"Normalization complete: {len(segments)} -> {len(out)} segments")
    return out


def format_seconds(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS.mmm for readability.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    else:
        return f"{minutes:02d}:{secs:06.3f}"
