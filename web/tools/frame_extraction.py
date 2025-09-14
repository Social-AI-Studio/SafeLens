import cv2
import os
import logging

logger = logging.getLogger(__name__)


def extract_frames(
    video_path,
    timestamps=None,
    start=None,
    end=None,
    fps=None,
    every_n_sec=None,
    output_dir="frames",
):
    """
    Extract frames from video using various methods

    Args:
        video_path: Path to video file
        timestamps: List of specific timestamps (seconds) to extract
        start: Start time for interval extraction (seconds)
        end: End time for interval extraction (seconds)
        fps: Frame rate for interval extraction (frames per second)
        every_n_sec: Extract every N seconds
        output_dir: Output directory for frames  # Updated parameter name

    Returns:
        List of paths to extracted frames
    """
    parent_folder = os.path.dirname(video_path)
    output_dir = os.path.join(parent_folder, output_dir)
    os.makedirs(output_dir, exist_ok=True)
    vidcap = cv2.VideoCapture(video_path)
    video_fps = vidcap.get(cv2.CAP_PROP_FPS)
    total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps

    frame_paths = []

    if timestamps:
        for ts in timestamps:
            success = False

            original_ts = max(0, min(ts, duration - 0.1))

            for retry_epsilon in [
                0.0,
                0.05,
                0.1,
                0.2,
            ]:
                try_ts = original_ts - retry_epsilon
                if try_ts < 0:
                    continue

                frame_index = int(try_ts * video_fps)
                frame_index = min(max(0, frame_index), total_frames - 1)

                vidcap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = vidcap.read()

                if success:
                    fname = os.path.join(
                        output_dir, f"frame_{int(original_ts * 1000)}.jpg"
                    )
                    cv2.imwrite(fname, frame)
                    frame_paths.append(fname)
                    break

                vidcap.set(cv2.CAP_PROP_POS_MSEC, try_ts * 1000)
                success, frame = vidcap.read()

                if success:
                    fname = os.path.join(
                        output_dir, f"frame_{int(original_ts * 1000)}.jpg"
                    )
                    cv2.imwrite(fname, frame)
                    frame_paths.append(fname)
                    break

            if not success:
                logger.warning(
                    f"Failed to extract frame at {ts:.1f}s (tried with epsilons up to 0.2s)"
                )

        return frame_paths

    if start is not None and end is not None and fps is not None:
        start = max(0, start)
        end = min(end, duration - 0.001)

        if start >= end:
            return []

        start_frame = int(start * video_fps)
        end_frame = int(end * video_fps)
        frame_step = int(video_fps / fps)

        for frame_index in range(start_frame, end_frame, frame_step):
            frame_index = min(frame_index, total_frames - 1)
            vidcap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = vidcap.read()
            if success:
                ts = frame_index / video_fps
                fname = os.path.join(output_dir, f"frame_{int(ts * 1000)}.jpg")
                cv2.imwrite(fname, frame)
                frame_paths.append(fname)
        return frame_paths

    if every_n_sec:
        interval = int(video_fps * every_n_sec)
        frame_paths = []
        count = 0

        while True:
            success, frame = vidcap.read()
            if not success:
                break
            if count % interval == 0:
                ts = count / video_fps
                if ts < duration:
                    fname = os.path.join(output_dir, f"frame_{int(ts * 1000)}.jpg")
                    cv2.imwrite(fname, frame)
                    frame_paths.append(fname)
            count += 1
        return frame_paths

    raise ValueError("No extraction method specified")
