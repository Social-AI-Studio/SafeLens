"""
Core segmentation module for partitioning videos into time segments.

Combines transcript sentence spans with visual scene-change detection
to create segments suitable for analysis.
"""
import logging
import math
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


def download_nltk_data():
    """Download required NLTK data if not present."""
    # Try punkt_tab first (newer NLTK versions)
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        logger.info("Downloading NLTK punkt_tab tokenizer")
        nltk.download('punkt_tab', quiet=True)
    
    # Fallback to punkt (older NLTK versions)
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        logger.info("Downloading NLTK punkt tokenizer")
        nltk.download('punkt', quiet=True)


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
                download_nltk_data()
                sentences = sent_tokenize(text)
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
        download_nltk_data()
        
        # Tokenize into sentences
        sentences = sent_tokenize(full_text)
        result_segments = []
        
        # Create word lookup for timing
        word_time_map = {}
        for word, time in word_timestamps:
            word_clean = word.lower().strip('.,!?;:"()[]{}')
            if word_clean not in word_time_map:
                word_time_map[word_clean] = []
            word_time_map[word_clean].append(time)
        
        full_text_lower = full_text.lower()
        char_pos = 0
        
        for sentence in sentences:
            if len(sentence.strip()) < min_chars:
                continue
                
            # Find sentence in full text
            sentence_start_char = full_text_lower.find(sentence.lower(), char_pos)
            if sentence_start_char == -1:
                continue
                
            sentence_end_char = sentence_start_char + len(sentence)
            char_pos = sentence_end_char
            
            # Map to word timings
            sentence_words = sentence.lower().split()
            sentence_words_clean = [w.strip('.,!?;:"()[]{}') for w in sentence_words if w.strip('.,!?;:"()[]{}')]
            
            if not sentence_words_clean:
                continue
                
            # Find start and end times
            start_time = None
            end_time = None
            
            # Find first word time
            for word in sentence_words_clean:
                if word in word_time_map and word_time_map[word]:
                    start_time = min(word_time_map[word])
                    break
            
            # Find last word time
            for word in reversed(sentence_words_clean):
                if word in word_time_map and word_time_map[word]:
                    end_time = max(word_time_map[word]) + 1.0  # Add duration estimate
                    break
            
            if start_time is not None and end_time is not None and end_time > start_time:
                result_segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': sentence.strip()
                })
        
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
    cache_key = f"{model_name}_{device}"
    
    if cache_key not in _vit_cache:
        logger.info(f"Loading ViT model {model_name} on {device}")
        try:
            processor = ViTImageProcessor.from_pretrained(model_name)
            model = ViTModel.from_pretrained(model_name)
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
    threshold: float = 0.85
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
            
        # Calculate sampling points
        sample_times = []
        current_time = start
        while current_time < end:
            sample_times.append(current_time)
            current_time += sampling_interval_sec
            
        if len(sample_times) < 2:
            logger.info("Not enough samples for boundary detection")
            return []
            
        logger.info(f"Sampling {len(sample_times)} frames at {sampling_interval_sec}s intervals")
        
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
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
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


def split_long_segment(
    seg: Dict,
    video_path: str,
    transcript: List[Dict],
    image_processor: ViTImageProcessor,
    vit_model: ViTModel,
    cfg: SegmentationConfig
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
    
    # Add visual boundaries
    visual_boundaries = find_visual_boundaries(
        video_path, start, end, image_processor, vit_model,
        cfg.sample_interval_sec, cfg.batch_size, cfg.scene_threshold
    )
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
    
    logger.info(f"Split into {len(result_segments)} segments")
    return result_segments


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
    cfg: SegmentationConfig
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
                        merged_seg, video_path, transcript, image_processor, vit_model, cfg
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
    
    # Load ViT model
    try:
        image_processor, vit_model = load_vit(cfg.vit_model, cfg.device)
    except Exception as e:
        logger.error(f"Failed to load ViT model: {e}")
        # Fallback to transcript-only processing
        segments = transcript_segments.copy()
    else:
        segments = transcript_segments.copy()
    
    # Sort segments by start time
    segments.sort(key=lambda x: x['start'])
    
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
        if 'image_processor' in locals() and 'vit_model' in locals():
            split_segments = []
            for seg in segments:
                duration = seg['end'] - seg['start']
                if duration > cfg.max_len_sec:
                    split_result = split_long_segment(
                        seg, video_path, transcript_segments, image_processor, vit_model, cfg
                    )
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
    if 'image_processor' in locals() and 'vit_model' in locals():
        segments = merge_tiny_segments(
            segments, video_path, transcript_segments, image_processor, vit_model, cfg
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
                logger.debug(f"Dropping tiny segment after trim: [{new_start:.1f}, {e:.1f}]")
                continue  # Too tiny after trim
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