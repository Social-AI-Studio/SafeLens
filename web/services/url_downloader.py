import yt_dlp
import logging
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class VideoURLDownloader:
    """Service for downloading videos from URLs using yt-dlp"""

    def __init__(self, download_dir: Path):
        """
        Initialize the downloader

        Args:
            download_dir: Base directory for video downloads
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download_video(self, url: str, video_id: str) -> Dict[str, Any]:
        """
        Download video from URL using yt-dlp

        Args:
            url: Video URL to download
            video_id: UUID for the video record

        Returns:
            Dict with success status, file path, metadata, and error info
        """
        video_dir = self.download_dir / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        output_path = str(video_dir / "video.%(ext)s")

        # yt-dlp configuration
        ydl_opts = {
            "outtmpl": output_path,
            "format": "best[ext=mp4][height<=1080]/best[ext=mp4]/best",  # Prefer MP4, max 1080p
            "extractaudio": False,
            "ignoreerrors": False,
            "no_warnings": False,
            "quiet": False,
            "max_filesize": 500 * 1024 * 1024,  # 500MB limit
            "noplaylist": True,  # Don't download playlists
            "restrictfilenames": True,  # Ensure safe filenames
            "writeinfojson": False,  # Don't write separate info JSON
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Extracting info for URL: {url}")

                info = ydl.extract_info(url, download=False)

                duration = info.get("duration", 0)
                if duration and duration > 3600:
                    raise ValueError(f"Video too long: {duration}s (max 1 hour)")

                extractor = info.get("extractor", "Unknown")
                logger.info(f"Video detected from {extractor}")

                logger.info(
                    f"Starting download for video: {info.get('title', 'Unknown')}"
                )

                ydl.download([url])

                downloaded_files = list(video_dir.glob("video.*"))
                if not downloaded_files:
                    raise RuntimeError("Download completed but file not found")

                video_file = downloaded_files[0]
                final_path = video_dir / "video.mp4"

                if video_file != final_path:
                    video_file.rename(final_path)

                if not final_path.exists() or final_path.stat().st_size == 0:
                    raise RuntimeError("Downloaded file is empty or missing")

                metadata = {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader", "Unknown"),
                    "upload_date": info.get("upload_date"),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "provider": info.get("extractor", "Unknown"),
                    "original_url": url,
                    "file_size": final_path.stat().st_size,
                    "format": info.get("format"),
                    "resolution": f"{info.get('width', 'Unknown')}x{info.get('height', 'Unknown')}",
                    "description": info.get("description", "")[:500]
                    if info.get("description")
                    else None,
                }

                logger.info(
                    f"Successfully downloaded video: {metadata['title']} ({metadata['file_size']} bytes)"
                )

                return {
                    "success": True,
                    "file_path": str(final_path),
                    "metadata": metadata,
                    "provider": info.get("extractor", "Unknown").lower(),
                }

        except yt_dlp.DownloadError as e:
            error_msg = f"yt-dlp download error: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "metadata": None,
                "provider": None,
            }
        except ValueError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "metadata": None,
                "provider": None,
            }
        except Exception as e:
            error_msg = f"Unexpected error during download: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "metadata": None,
                "provider": None,
            }

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
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    "success": True,
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader", "Unknown"),
                    "provider": info.get("extractor", "Unknown"),
                    "thumbnail": info.get("thumbnail"),
                    "estimated_size": None,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

