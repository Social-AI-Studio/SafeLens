import yt_dlp
import logging
import subprocess
import time
import re
import shutil
import os
import importlib.util
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass

logger = logging.getLogger(__name__)
_warned_missing_ytdlp_ejs = False


class DownloadErrorCode(str, Enum):
    """Structured error codes for frontend-friendly error handling"""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    UNSUPPORTED_FORMAT = "unsupported_format"
    TOO_LARGE = "too_large"
    TOO_LONG = "too_long"
    LIVE_STREAM = "live_stream"
    UNAVAILABLE = "unavailable"
    AGE_RESTRICTED = "age_restricted"
    MEMBERS_ONLY = "members_only"
    GEO_BLOCKED = "geo_blocked"
    DRM_PROTECTED = "drm_protected"
    PRIVATE_VIDEO = "private_video"
    NOT_FOUND = "not_found"
    NETWORK_ERROR = "network_error"
    FFMPEG_MISSING = "ffmpeg_missing"
    FFMPEG_ERROR = "ffmpeg_error"
    INVALID_URL = "invalid_url"
    EXTRACTION_FAILED = "extraction_failed"
    DOWNLOAD_FAILED = "download_failed"
    UNKNOWN_ERROR = "unknown_error"


ERROR_MESSAGES = {
    DownloadErrorCode.RATE_LIMITED: "Too many requests. Please try again in a few minutes.",
    DownloadErrorCode.UNSUPPORTED_FORMAT: "This video format is not supported.",
    DownloadErrorCode.TOO_LARGE: "Video file is too large (max 500MB).",
    DownloadErrorCode.TOO_LONG: "Video is too long (max 1 hour).",
    DownloadErrorCode.LIVE_STREAM: "Live streams cannot be downloaded.",
    DownloadErrorCode.UNAVAILABLE: "This video is not available.",
    DownloadErrorCode.AGE_RESTRICTED: "This video is age-restricted and requires authentication.",
    DownloadErrorCode.MEMBERS_ONLY: "This video is only available to channel members.",
    DownloadErrorCode.GEO_BLOCKED: "This video is not available in your region.",
    DownloadErrorCode.DRM_PROTECTED: "This video is DRM-protected and cannot be downloaded.",
    DownloadErrorCode.PRIVATE_VIDEO: "This video is private.",
    DownloadErrorCode.NOT_FOUND: "Video not found. The URL may be invalid or the video was deleted.",
    DownloadErrorCode.NETWORK_ERROR: "Network error occurred. Please check your connection and try again.",
    DownloadErrorCode.FFMPEG_MISSING: "FFmpeg is not installed. Video processing is unavailable.",
    DownloadErrorCode.FFMPEG_ERROR: "Video processing failed. Please try a different video.",
    DownloadErrorCode.INVALID_URL: "Invalid URL format.",
    DownloadErrorCode.EXTRACTION_FAILED: "Could not extract video information from URL.",
    DownloadErrorCode.DOWNLOAD_FAILED: "Download failed. Please try again.",
    DownloadErrorCode.UNKNOWN_ERROR: "An unexpected error occurred.",
}


@dataclass
class DownloadResult:
    """Structured result from download operations"""

    success: bool
    error_code: DownloadErrorCode
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    retry_after: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error_code": self.error_code.value,
            "error": self.error_message,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "provider": self.provider,
            "retry_after": self.retry_after,
        }


RETRYABLE_ERRORS = [
    "HTTP Error 429",
    "HTTP Error 500",
    "HTTP Error 502",
    "HTTP Error 503",
    "HTTP Error 504",
    "Connection reset",
    "Connection refused",
    "Connection timed out",
    "timed out",
    "Temporary failure",
    "Network is unreachable",
    "fragment",
    "urlopen error",
]


class VideoURLDownloader:
    """Service for downloading videos from URLs using yt-dlp"""

    DEFAULT_FORMAT = (
        "bv*[ext=mp4][height<=1080][vcodec^=avc1]+ba[acodec^=mp4a]/"
        "bv*[height<=1080]+ba/"
        "b[ext=mp4][height<=1080]/"
        "b[height<=1080]/"
        "best"
    )
    PROGRESSIVE_FALLBACK_FORMAT = "22/18/best"

    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_DURATION = 3600  # 1 hour in seconds
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2  # seconds

    def __init__(
        self,
        download_dir: Path,
        cookie_file: Optional[Path] = None,
        proxy: Optional[str] = None,
        android_po_token: Optional[str] = None,
    ):
        """
        Initialize the downloader

        Args:
            download_dir: Base directory for video downloads
            cookie_file: Optional path to cookies.txt for authenticated downloads
            proxy: Optional proxy URL (e.g., "socks5://127.0.0.1:1080")
            android_po_token: Optional PO token for Android client to improve HTTPS availability
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = cookie_file
        self.proxy = proxy
        self.android_po_token = android_po_token
        self._ffmpeg_available: Optional[bool] = None

    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available on the system"""
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available

        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._ffmpeg_available = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            self._ffmpeg_available = False

        if not self._ffmpeg_available:
            logger.warning("FFmpeg not found. Video remuxing will be unavailable.")

        return self._ffmpeg_available

    def normalize_url(self, url: str) -> str:
        """
        Normalize video URLs to their canonical form

        Handles:
        - YouTube Shorts (/shorts/X → /watch?v=X)
        - YouTube short URLs (youtu.be/X → youtube.com/watch?v=X)
        - Removes unnecessary parameters
        """
        parsed = urlparse(url)
        hostname = parsed.netloc.lower().replace("www.", "")

        if hostname in ["youtube.com", "youtu.be", "m.youtube.com"]:
            if "/shorts/" in parsed.path:
                video_id = parsed.path.split("/shorts/")[1].split("/")[0].split("?")[0]
                return f"https://www.youtube.com/watch?v={video_id}"

            if hostname == "youtu.be":
                video_id = parsed.path.lstrip("/").split("/")[0].split("?")[0]
                return f"https://www.youtube.com/watch?v={video_id}"

            if "/live/" in parsed.path:
                video_id = parsed.path.split("/live/")[1].split("/")[0].split("?")[0]
                return f"https://www.youtube.com/watch?v={video_id}"

        return url

    def _cleanup_video_dir(self, video_dir: Path) -> None:
        """Clean up video directory before download to remove stale files"""
        if video_dir.exists():
            for pattern in ["video.*", "*.part", "*.ytdl", "*.temp", "*.tmp"]:
                for file in video_dir.glob(pattern):
                    try:
                        file.unlink()
                        logger.debug(f"Cleaned up stale file: {file}")
                    except OSError as e:
                        logger.warning(f"Failed to clean up {file}: {e}")

    def _is_retryable_error(self, error_str: str) -> bool:
        """Check if an error is transient and worth retrying"""
        error_lower = error_str.lower()
        return any(retryable.lower() in error_lower for retryable in RETRYABLE_ERRORS)

    def _classify_error(self, error: Exception, error_str: str) -> DownloadErrorCode:
        """Classify an error into a structured error code"""
        error_lower = error_str.lower()

        if "429" in error_str or "rate" in error_lower:
            return DownloadErrorCode.RATE_LIMITED

        if "403" in error_str and "age" in error_lower:
            return DownloadErrorCode.AGE_RESTRICTED

        if "members" in error_lower or "member" in error_lower:
            return DownloadErrorCode.MEMBERS_ONLY

        if "private" in error_lower:
            return DownloadErrorCode.PRIVATE_VIDEO

        if "404" in error_str or "not found" in error_lower or "unavailable" in error_lower:
            return DownloadErrorCode.NOT_FOUND

        if "geo" in error_lower or "country" in error_lower or "region" in error_lower:
            return DownloadErrorCode.GEO_BLOCKED

        if "drm" in error_lower or "widevine" in error_lower:
            return DownloadErrorCode.DRM_PROTECTED

        if "format" in error_lower or "codec" in error_lower:
            return DownloadErrorCode.UNSUPPORTED_FORMAT

        if any(net_err in error_lower for net_err in ["connection", "network", "timeout", "timed out"]):
            return DownloadErrorCode.NETWORK_ERROR

        if "postprocess" in error_lower or "ffmpeg" in error_lower:
            return DownloadErrorCode.FFMPEG_ERROR

        if isinstance(error, yt_dlp.DownloadError):
            return DownloadErrorCode.DOWNLOAD_FAILED

        return DownloadErrorCode.UNKNOWN_ERROR

    def _validate_video_info(self, info: Dict[str, Any]) -> Optional[DownloadResult]:
        """
        Pre-download validation of video info

        Returns None if validation passes, or a DownloadResult with error if it fails
        """
        is_live = info.get("is_live") or info.get("live_status") == "is_live"
        if is_live:
            return DownloadResult(
                success=False,
                error_code=DownloadErrorCode.LIVE_STREAM,
                error_message=ERROR_MESSAGES[DownloadErrorCode.LIVE_STREAM],
            )

        availability = info.get("availability")
        if availability:
            if availability == "needs_auth":
                return DownloadResult(
                    success=False,
                    error_code=DownloadErrorCode.AGE_RESTRICTED,
                    error_message=ERROR_MESSAGES[DownloadErrorCode.AGE_RESTRICTED],
                )
            if availability == "subscriber_only":
                return DownloadResult(
                    success=False,
                    error_code=DownloadErrorCode.MEMBERS_ONLY,
                    error_message=ERROR_MESSAGES[DownloadErrorCode.MEMBERS_ONLY],
                )
            if availability == "premium_only":
                return DownloadResult(
                    success=False,
                    error_code=DownloadErrorCode.MEMBERS_ONLY,
                    error_message="This video requires a premium subscription.",
                )
            if availability in ["private", "unlisted_private"]:
                return DownloadResult(
                    success=False,
                    error_code=DownloadErrorCode.PRIVATE_VIDEO,
                    error_message=ERROR_MESSAGES[DownloadErrorCode.PRIVATE_VIDEO],
                )

        duration = info.get("duration", 0)
        if duration and duration > self.MAX_DURATION:
            return DownloadResult(
                success=False,
                error_code=DownloadErrorCode.TOO_LONG,
                error_message=f"Video is {duration // 60} minutes long (max {self.MAX_DURATION // 60} minutes).",
            )

        filesize = info.get("filesize") or info.get("filesize_approx")
        if filesize and filesize > self.MAX_FILE_SIZE:
            size_mb = filesize / (1024 * 1024)
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return DownloadResult(
                success=False,
                error_code=DownloadErrorCode.TOO_LARGE,
                error_message=f"Video is approximately {size_mb:.0f}MB (max {max_mb:.0f}MB).",
            )

        return None

    def _get_ydl_opts(
        self,
        output_path: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        format_override: Optional[str] = None,
        player_client: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build yt-dlp options with all enhancements"""
        format_str = format_override or self.DEFAULT_FORMAT

        opts = {
            "outtmpl": output_path,
            "format": format_str,
            "merge_output_format": "mp4",
            "extractaudio": False,
            "ignoreerrors": False,
            "no_warnings": False,
            "quiet": False,
            "max_filesize": self.MAX_FILE_SIZE,
            "noplaylist": True,
            "restrictfilenames": True,
            "writeinfojson": False,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 3,
            "extractor_retries": 3,
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_requests": 1,
            "postprocessors": [],
        }

        # Ensure yt-dlp can use a JS runtime when YouTube challenges require it.
        # In newer yt-dlp versions, this is controlled via --js-runtimes, not --js-interpreter.
        deno_path = shutil.which("deno")
        if deno_path:
            opts.setdefault("js_runtimes", {})
            opts["js_runtimes"].setdefault("deno", {"path": deno_path})

        global _warned_missing_ytdlp_ejs
        if not _warned_missing_ytdlp_ejs:
            if importlib.util.find_spec("yt_dlp_ejs") is None:
                _warned_missing_ytdlp_ejs = True
                logger.warning(
                    "yt-dlp-ejs is not installed; YouTube JS/EJS challenges may hide video formats "
                    "and cause low-quality fallbacks. Rebuild the web base image to pick up updated deps, "
                    "or set YTDLP_REMOTE_COMPONENTS=ejs:github (supply-chain tradeoff)."
                )

        # Optional: allow fetching yt-dlp-ejs remote components (can reduce "challenge solving failed").
        # Keep this opt-in because it pulls code at runtime.
        remote_components = os.getenv("YTDLP_REMOTE_COMPONENTS", "").strip()
        if remote_components:
            components = {
                c.strip()
                for c in remote_components.split(",")
                if isinstance(c, str) and c.strip()
            }
            if components:
                opts["remote_components"] = components

        if self.check_ffmpeg():
            opts["postprocessors"].append(
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            )

        if self.cookie_file and self.cookie_file.exists():
            opts["cookiefile"] = str(self.cookie_file)

        if self.proxy:
            opts["proxy"] = self.proxy

        if progress_callback:
            opts["progress_hooks"] = [progress_callback]

        extractor_args: Dict[str, Dict[str, Any]] = {}
        if player_client:
            extractor_args["youtube"] = {"player_client": [player_client]}
            if player_client == "android" and self.android_po_token:
                extractor_args["youtube"]["po_token"] = [self.android_po_token]

        if extractor_args:
            opts["extractor_args"] = extractor_args

        return opts

    @staticmethod
    def _info_has_video_stream(info: Dict[str, Any]) -> bool:
        """
        Best-effort check that the extractor returned at least one format with video.

        This prevents us from "successfully" downloading audio-only when YouTube/EJS
        challenges hide video formats.
        """
        formats = info.get("formats") or []
        if not isinstance(formats, list):
            return False
        for fmt in formats:
            if not isinstance(fmt, dict):
                continue
            vcodec = fmt.get("vcodec")
            # Some challenge-failure cases still return formats, but without a downloadable URL.
            if (
                isinstance(vcodec, str)
                and vcodec != "none"
                and isinstance(fmt.get("url"), str)
                and fmt.get("url")
            ):
                return True
        return False

    def _file_has_video_stream(self, path: Path) -> bool:
        """Verify the downloaded artifact actually contains a video stream."""
        if not self.check_ffmpeg():
            # If ffmpeg/ffprobe aren't available, fall back to trusting yt-dlp.
            return True
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "csv=p=0",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            return bool(result.stdout.strip())
        except Exception:
            return True

    def _ffprobe_stream_summary(self, path: Path) -> Dict[str, Any]:
        """Best-effort media probe for debugging download quality."""
        if not self.check_ffmpeg():
            return {"ok": False, "error": "ffprobe_unavailable"}
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=index,codec_type,codec_name,width,height,avg_frame_rate,channels,sample_rate",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                return {"ok": False, "error": result.stderr.strip() or "ffprobe_failed"}
            import json

            payload = json.loads(result.stdout or "{}")
            streams = payload.get("streams") if isinstance(payload, dict) else None
            if not isinstance(streams, list):
                return {"ok": False, "error": "no_streams"}

            video = next(
                (
                    s
                    for s in streams
                    if isinstance(s, dict) and s.get("codec_type") == "video"
                ),
                None,
            )
            audio = next(
                (
                    s
                    for s in streams
                    if isinstance(s, dict) and s.get("codec_type") == "audio"
                ),
                None,
            )
            summary: Dict[str, Any] = {"ok": True}
            if isinstance(video, dict):
                summary["video"] = {
                    "codec": video.get("codec_name"),
                    "width": video.get("width"),
                    "height": video.get("height"),
                    "fps": video.get("avg_frame_rate"),
                }
            if isinstance(audio, dict):
                summary["audio"] = {
                    "codec": audio.get("codec_name"),
                    "channels": audio.get("channels"),
                    "sample_rate": audio.get("sample_rate"),
                }
            return summary
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def download_video(
        self,
        url: str,
        video_id: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> DownloadResult:
        """
        Download video from URL using yt-dlp with retries and validation

        Args:
            url: Video URL to download
            video_id: UUID for the video record
            progress_callback: Optional callback for progress updates

        Returns:
            DownloadResult with success status, file path, metadata, and error info
        """
        if not self.check_ffmpeg():
            logger.warning("FFmpeg not available, downloads may fail for some formats")

        original_url = url
        url = self.normalize_url(url)
        video_dir = self.download_dir / video_id

        self._cleanup_video_dir(video_dir)
        video_dir.mkdir(parents=True, exist_ok=True)

        output_path = str(video_dir / "video.%(ext)s")

        last_error: Optional[str] = None
        last_error_code = DownloadErrorCode.UNKNOWN_ERROR

        web_profile = {
            "name": "web",
            "player_client": None,
            "format": self.DEFAULT_FORMAT,
        }
        ios_profile = {
            "name": "ios",
            "player_client": "ios",
            "format": self.DEFAULT_FORMAT,
        }
        android_profile = {
            "name": "android",
            "player_client": "android",
            # Prefer best <=1080p first; fall back to progressive-only itags (22/18) if needed.
            "format": f"{self.DEFAULT_FORMAT}/{self.PROGRESSIVE_FALLBACK_FORMAT}",
        }

        # Web is the most stable / lowest-maintenance default (no PO token dependency).
        # Android is kept as a last resort because higher-quality HTTPS formats increasingly
        # require a PO token; without it, yt-dlp may fall back to very low-res progressive itags.
        client_profiles = [web_profile, ios_profile, android_profile]

        for attempt in range(1, self.MAX_RETRIES + 1):
            profile = client_profiles[min(attempt - 1, len(client_profiles) - 1)]
            ydl_opts = self._get_ydl_opts(
                output_path,
                progress_callback,
                format_override=profile["format"],
                player_client=profile["player_client"],
            )

            try:
                self._cleanup_video_dir(video_dir)

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(
                        f"Attempt {attempt}/{self.MAX_RETRIES} using {profile['name']} client: Extracting info for URL: {url}"
                    )

                    info = ydl.extract_info(url, download=False)
                    if info is None:
                        return DownloadResult(
                            success=False,
                            error_code=DownloadErrorCode.EXTRACTION_FAILED,
                            error_message=ERROR_MESSAGES[DownloadErrorCode.EXTRACTION_FAILED],
                        )

                    validation_error = self._validate_video_info(info)
                    if validation_error:
                        return validation_error

                    extractor = info.get("extractor", "Unknown")
                    title = info.get("title", "Unknown")
                    logger.info(f"Video detected from {extractor}: {title}")

                    if not self._info_has_video_stream(info):
                        last_error = (
                            "Extractor returned no video formats; likely blocked by YouTube JS/EJS challenges"
                        )
                        last_error_code = DownloadErrorCode.EXTRACTION_FAILED
                        if attempt < self.MAX_RETRIES:
                            logger.warning(
                                f"{last_error}. Retrying with fallback client..."
                            )
                            continue
                        logger.error(last_error)
                        break

                    logger.info(f"Starting download for video: {title}")
                    # Avoid re-extracting info (which can trigger extra JS challenge failures).
                    result_info = ydl.process_ie_result(info, download=True) or info

                    # Log selected formats if yt-dlp exposes them (varies by extractor/version).
                    try:
                        requested = None
                        if isinstance(result_info, dict):
                            requested = result_info.get("requested_formats")
                            if requested is None:
                                requested = result_info.get("requested_downloads")

                        selected_ids = []
                        if isinstance(requested, list):
                            for it in requested:
                                if isinstance(it, dict) and it.get("format_id"):
                                    selected_ids.append(str(it.get("format_id")))
                        elif isinstance(requested, dict) and requested.get("format_id"):
                            selected_ids.append(str(requested.get("format_id")))
                        elif isinstance(result_info, dict) and result_info.get("format_id"):
                            selected_ids.append(str(result_info.get("format_id")))

                        if selected_ids:
                            logger.info(
                                f"yt-dlp selected format_id(s): {','.join(selected_ids)}"
                            )
                    except Exception:
                        pass

                    downloaded_files = list(video_dir.glob("video.*"))
                    downloaded_files = [f for f in downloaded_files if not f.suffix in [".part", ".ytdl", ".temp"]]

                    if not downloaded_files:
                        raise RuntimeError("Download completed but file not found")

                    video_file = max(downloaded_files, key=lambda p: p.stat().st_size)
                    final_path = video_dir / "video.mp4"

                    if not self._file_has_video_stream(video_file):
                        last_error = (
                            f"Downloaded artifact has no video stream (likely YouTube challenge failure): {video_file.name}"
                        )
                        last_error_code = DownloadErrorCode.EXTRACTION_FAILED
                        if attempt < self.MAX_RETRIES:
                            logger.warning(f"{last_error}. Retrying with fallback client...")
                            continue
                        logger.error(last_error)
                        break

                    if video_file.suffix != ".mp4":
                        if self.check_ffmpeg():
                            logger.info(f"Remuxing {video_file.suffix} to mp4")
                            try:
                                subprocess.run(
                                    [
                                        "ffmpeg",
                                        "-i",
                                        str(video_file),
                                        "-c",
                                        "copy",
                                        "-y",
                                        str(final_path),
                                    ],
                                    capture_output=True,
                                    check=True,
                                    timeout=300,
                                )
                                video_file.unlink()
                            except subprocess.CalledProcessError as e:
                                logger.warning(f"FFmpeg remux failed: {e}, attempting transcode")
                                try:
                                    subprocess.run(
                                        [
                                            "ffmpeg",
                                            "-i",
                                            str(video_file),
                                            "-c:v",
                                            "copy",
                                            "-c:a",
                                            "aac",
                                            "-b:a",
                                            "192k",
                                            "-y",
                                            str(final_path),
                                        ],
                                        capture_output=True,
                                        check=True,
                                        timeout=600,
                                    )
                                    video_file.unlink()
                                except subprocess.CalledProcessError as e2:
                                    logger.warning(f"FFmpeg transcode also failed: {e2}, keeping original extension")
                                    final_path = video_dir / f"video{video_file.suffix}"
                                    if video_file != final_path:
                                        video_file.rename(final_path)
                        else:
                            logger.warning(f"FFmpeg not available, keeping original extension {video_file.suffix}")
                            final_path = video_dir / f"video{video_file.suffix}"
                            if video_file != final_path:
                                video_file.rename(final_path)
                    elif video_file != final_path:
                        video_file.rename(final_path)

                    if not final_path.exists():
                        raise RuntimeError("Final video file not found after processing")

                    file_size = final_path.stat().st_size
                    if file_size == 0:
                        raise RuntimeError("Downloaded file is empty")

                    # Log actual on-disk media characteristics for debugging/resolution checks.
                    probe = self._ffprobe_stream_summary(final_path)
                    if probe.get("ok") is True:
                        logger.info(f"Downloaded media probe: {probe}")
                    else:
                        logger.debug(f"ffprobe failed for downloaded media: {probe}")

                    expected_size = info.get("filesize") or info.get("filesize_approx")
                    if expected_size and file_size < expected_size * 0.5:
                        logger.warning(
                            f"Downloaded file size ({file_size}) is much smaller than expected ({expected_size})"
                        )

                    metadata = {
                        "title": info.get("title", "Unknown"),
                        "duration": info.get("duration"),
                        "uploader": info.get("uploader", "Unknown"),
                        "upload_date": info.get("upload_date"),
                        "view_count": info.get("view_count"),
                        "like_count": info.get("like_count"),
                        "provider": info.get("extractor", "Unknown"),
                        "original_url": original_url,
                        "file_size": file_size,
                        "format": info.get("format"),
                        "resolution": f"{info.get('width', 'Unknown')}x{info.get('height', 'Unknown')}",
                        "description": (info.get("description", "")[:500] if info.get("description") else None),
                    }

                    logger.info(f"Successfully downloaded video: {metadata['title']} ({file_size} bytes)")

                    return DownloadResult(
                        success=True,
                        error_code=DownloadErrorCode.SUCCESS,
                        file_path=str(final_path),
                        metadata=metadata,
                        provider=info.get("extractor", "Unknown").lower(),
                    )

            except yt_dlp.DownloadError as e:
                error_str = str(e)
                last_error = error_str
                last_error_code = self._classify_error(e, error_str)

                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1)) if self._is_retryable_error(error_str) else None
                    if delay:
                        logger.warning(f"Retryable error on attempt {attempt}: {error_str}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.info(f"Retrying with fallback client after error: {error_str}")
                    continue

                logger.error(f"yt-dlp download error: {error_str}")
                break

            except yt_dlp.utils.PostProcessingError as e:
                error_str = str(e)
                last_error = f"Post-processing error: {error_str}"
                last_error_code = DownloadErrorCode.FFMPEG_ERROR
                logger.error(last_error)
                break

            except ValueError as e:
                error_str = str(e)
                last_error = f"Validation error: {error_str}"
                last_error_code = DownloadErrorCode.UNKNOWN_ERROR
                logger.error(last_error)
                break

            except Exception as e:
                error_str = str(e)
                last_error = error_str
                last_error_code = self._classify_error(e, error_str)

                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1)) if self._is_retryable_error(error_str) else None
                    if delay:
                        logger.warning(f"Retryable error on attempt {attempt}: {error_str}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.info(f"Retrying with fallback client after error: {error_str}")
                    continue

                logger.error(f"Unexpected error during download: {error_str}")
                break

        user_friendly_message = ERROR_MESSAGES.get(last_error_code, "Download failed. Please try again.")
        logger.debug(f"Raw error for {last_error_code}: {last_error}")
        
        return DownloadResult(
            success=False,
            error_code=last_error_code,
            error_message=user_friendly_message,
            retry_after=60 if last_error_code == DownloadErrorCode.RATE_LIMITED else None,
        )

    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is acceptable for download

        Args:
            url: URL to validate

        Returns:
            True if URL is valid for download
        """
        try:
            parsed = urlparse(url)

            if parsed.scheme not in ["http", "https"]:
                return False

            if not parsed.netloc:
                return False

            return True
        except Exception:
            return False

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Extract video info without downloading

        Args:
            url: Video URL

        Returns:
            Dict with video metadata or error info
        """
        url = self.normalize_url(url)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        if self.cookie_file and self.cookie_file.exists():
            ydl_opts["cookiefile"] = str(self.cookie_file)

        if self.proxy:
            ydl_opts["proxy"] = self.proxy

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info is None:
                    return {
                        "success": False,
                        "error": "Could not extract video information",
                        "error_code": DownloadErrorCode.EXTRACTION_FAILED.value,
                    }

                validation_error = self._validate_video_info(info)
                if validation_error:
                    return {
                        "success": False,
                        "error": validation_error.error_message,
                        "error_code": validation_error.error_code.value,
                    }

                return {
                    "success": True,
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader", "Unknown"),
                    "provider": info.get("extractor", "Unknown"),
                    "thumbnail": info.get("thumbnail"),
                    "estimated_size": info.get("filesize") or info.get("filesize_approx"),
                    "is_live": info.get("is_live", False),
                    "availability": info.get("availability"),
                }
        except Exception as e:
            error_code = self._classify_error(e, str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": error_code.value,
            }
