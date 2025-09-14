import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    File,
    UploadFile,
    HTTPException,
    Depends,
    Header,
    BackgroundTasks,
    Form,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import validators

from ..database import get_db, Account, Video
from ..services.url_downloader import VideoURLDownloader
from ..schemas.responses import (
    VideoInfo,
    UploadResponse,
    VideoListResponse,
    UserVideoResponse,
    AnalysisStatus,
    AnalysisResult,
    URLDownloadRequest,
    URLDownloadResponse,
    DownloadStatusResponse,
)
from ..background.enqueue import enqueue_analysis

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_FOLDER = Path("./videos")
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv", ".wmv"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

UPLOAD_FOLDER.mkdir(exist_ok=True)

downloader = VideoURLDownloader(UPLOAD_FOLDER)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_account_by_session_uuid(session_uuid: str, db: Session) -> Account:
    """
    Get account by session UUID (Auth.js UUID) and return the account with CUID v2
    This provides the UUID -> CUID v2 mapping for security
    """
    account = db.query(Account).filter(Account.session_uuid == session_uuid).first()
    if not account:
        raise HTTPException(
            status_code=401, detail="User session not found. Please sign in again."
        )
    return account


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    analysis_model: str = Form(
        ..., description="Analysis model to use for video processing"
    ),
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Handle video file upload"""

    logger.info("Upload request received")
    logger.info(f"File: {file.filename if file else 'None'}")
    logger.info(f"analysis_model parameter: '{analysis_model}'")
    logger.info(f"analysis_model type: {type(analysis_model)}")
    logger.info(f"user_id: {user_id}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    account = get_account_by_session_uuid(user_id, db)

    video_id = str(uuid.uuid4())
    video_dir = UPLOAD_FOLDER / video_id
    video_dir.mkdir(exist_ok=True)

    video_path = video_dir / "video.mp4"
    with open(video_path, "wb") as f:
        f.write(content)

    try:
        from ..tools.frame_extraction import extract_frames

        frames_output = extract_frames(
            video_path=str(video_path),
            timestamps=[0],  # Extract frame at 0 seconds for thumbnail
            output_dir="frames",
        )
        logger.info(f"Created thumbnail for uploaded video {video_id}: {frames_output}")
    except Exception as e:
        logger.warning(f"Failed to create thumbnail for uploaded video {video_id}: {e}")

    video = Video(
        id=video_id,
        account_id=account.id,
        original_filename=file.filename,
        file_size=file_size,
        file_path=str(video_path),
        analysis_model=analysis_model,
        source_type="upload",
        download_status="completed",
    )
    db.add(video)
    db.commit()

    metadata = {
        "video_id": video_id,
        "original_filename": file.filename,
        "file_size": file_size,
        "upload_timestamp": datetime.now().isoformat(),
        "file_path": str(video_path),
        "status": "uploaded",
    }

    metadata_path = video_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return UploadResponse(
        video_id=video_id,
        filename=file.filename,
        status="success",
        message="Video uploaded successfully",
        path=str(video_path),
    )


@router.get("/videos", response_model=VideoListResponse)
async def list_videos():
    """List all uploaded videos"""
    videos = []

    for video_dir in UPLOAD_FOLDER.iterdir():
        if video_dir.is_dir():
            metadata_file = video_dir / "metadata.json"
            video_file = video_dir / "video.mp4"

            if metadata_file.exists() and video_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                        videos.append(VideoInfo(**metadata))
                except Exception:
                    continue

    return VideoListResponse(videos=videos, count=len(videos))


@router.get("/user/videos", response_model=List[UserVideoResponse])
async def get_user_videos(
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Get videos for the authenticated user with summary information"""
    account = get_account_by_session_uuid(user_id, db)

    videos = (
        db.query(Video)
        .filter(Video.account_id == account.id)
        .order_by(Video.uploaded_at.desc())
        .all()
    )

    return [
        UserVideoResponse(
            video_id=video.id,
            original_filename=video.original_filename,
            file_size=video.file_size,
            uploaded_at=video.uploaded_at,
            analysis_status=video.analysis_status,
            duration=video.duration,
            safety_rating=video.safety_rating,
            harmful_events_count=video.harmful_events_count,
            overall_confidence_score=video.overall_confidence_score,
            summary=video.summary,
            thumbnail_url=f"/api/videos/{video.id}/thumbnail.jpg",
        )
        for video in videos
    ]


@router.get("/videos/{video_id}", response_model=VideoInfo)
async def get_video_info(video_id: str):
    """Get specific video information"""
    video_dir = UPLOAD_FOLDER / video_id
    metadata_file = video_dir / "metadata.json"

    if not video_dir.exists() or not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
            return VideoInfo(**metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{video_id}/video.mp4")
async def serve_video(video_id: str):
    """Serve video file for playback"""
    video_dir = UPLOAD_FOLDER.resolve() / video_id
    video_file = video_dir / "video.mp4"

    logger.debug(f"Looking for video file at: {video_file}")
    logger.debug(f"File exists: {video_file.exists()}")
    logger.debug(f"Working directory: {Path.cwd()}")

    if not video_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Video file not found: {video_file}"
        )

    return FileResponse(str(video_file), media_type="video/mp4")


@router.get("/videos/{video_id}/thumbnail.jpg")
async def serve_thumbnail(video_id: str):
    """Serve thumbnail image for a video"""
    video_dir = UPLOAD_FOLDER.resolve() / video_id
    thumbnail_file = video_dir / "frames" / "frame_0.jpg"

    if not thumbnail_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Thumbnail not found: {thumbnail_file}"
        )

    return FileResponse(str(thumbnail_file), media_type="image/jpeg")


@router.post("/analyze/{video_id}")
async def trigger_analysis(
    video_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Trigger video analysis for a specific video"""

    account = get_account_by_session_uuid(user_id, db)

    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.account_id == account.id)
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found or access denied")

    if video.analysis_status == "processing":
        raise HTTPException(status_code=409, detail="Analysis already in progress")

    if video.analysis_status == "completed":
        raise HTTPException(status_code=409, detail="Analysis already completed")

    video_path = str(video.file_path)
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    video.analysis_status = "pending"
    db.commit()

    enqueue_analysis(background_tasks, video_id)

    return {
        "video_id": video_id,
        "status": "analysis_triggered",
        "message": "Video analysis has been queued",
    }


@router.get("/analyze/{video_id}/status", response_model=AnalysisStatus)
async def get_analysis_status(
    video_id: str,
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Get analysis status for a specific video"""

    account = get_account_by_session_uuid(user_id, db)

    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.account_id == account.id)
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found or access denied")

    return AnalysisStatus(
        video_id=video_id,
        status=str(video.analysis_status),
        message=f"Analysis is {video.analysis_status}",
        started_at=video.uploaded_at,
        completed_at=None,
    )


@router.get("/analyze/{video_id}/results", response_model=AnalysisResult)
async def get_analysis_results(
    video_id: str,
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Get analysis results for a specific video"""

    account = get_account_by_session_uuid(user_id, db)

    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.account_id == account.id)
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found or access denied")

    if video.analysis_status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Analysis not completed. Current status: {video.analysis_status}",
        )

    try:
        if video.safety_report:
            parsed = json.loads(str(video.safety_report))
            if isinstance(parsed, dict) and parsed.get("format_version") == 2:
                logger.info(f"Returning v2 report for video {video_id}")

                transcript_data = None

                video_dir = Path("./videos") / video_id
                transcript_file = video_dir / "transcript.json"

                if transcript_file.exists():
                    try:
                        with open(transcript_file, "r") as f:
                            transcript_cache = json.load(f)
                            transcript_data = {
                                "full_text": transcript_cache.get("full_text", ""),
                                "word_timestamps": transcript_cache.get(
                                    "word_timestamps", []
                                ),
                            }
                    except Exception as e:
                        logger.warning(
                            f"Failed to read cached transcript for video {video_id}: {e}"
                        )

                if not transcript_data and video.transcription:
                    try:
                        word_timestamps = (
                            json.loads(video.transcription.word_timestamps)
                            if video.transcription.word_timestamps
                            else []
                        )
                    except (json.JSONDecodeError, TypeError):
                        word_timestamps = []

                    transcript_data = {
                        "full_text": video.transcription.full_text or "",
                        "word_timestamps": word_timestamps,
                    }

                if transcript_data:
                    parsed["transcription"] = transcript_data
                else:
                    parsed["transcription"] = {"full_text": "", "word_timestamps": []}

                return AnalysisResult(
                    video_id=video_id,
                    status="completed",
                    safety_report=parsed,
                    created_at=video.uploaded_at,
                )
    except Exception as e:
        logger.warning(f"Failed to parse v2 report for video {video_id}: {e}")

    logger.info(f"Building DB fallback report for video {video_id}")
    try:
        harmful_events = []
        for event in video.harmful_events:
            visual_evidence = None
            if event.visual_evidence:
                visual_evidence = {
                    "ocr_text": event.visual_evidence[0].ocr_text
                    if event.visual_evidence
                    else None,
                    "image_labels": [
                        {
                            "label": label.label,
                            "category": label.category,
                            "confidence": label.confidence,
                        }
                        for visual in event.visual_evidence
                        for label in visual.image_labels
                    ]
                    if event.visual_evidence
                    else [],
                }

            audio_evidence = (
                [
                    {"transcript_snippet": audio.transcript_snippet}
                    for audio in event.audio_evidence
                ]
                if event.audio_evidence
                else []
            )

            harmful_events.append(
                {
                    "id": event.id,
                    "timestamp": event.timestamp,
                    "categories": json.loads(event.categories)
                    if event.categories
                    else [],
                    "verification_source": event.verification_source,
                    "explanation": event.explanation,
                    "confidence_score": event.confidence_score,
                    "severity": event.severity,
                    "visual_evidence": visual_evidence,
                    "audio_evidence": audio_evidence,
                }
            )

        transcription = None
        if video.transcription:
            transcription = {
                "full_text": video.transcription.full_text,
                "word_timestamps": json.loads(video.transcription.word_timestamps)
                if video.transcription.word_timestamps
                else [],
            }

        safety_report = {
            "video_metadata": {
                "duration": video.duration,
                "safety_rating": video.safety_rating,
                "harmful_events_count": video.harmful_events_count,
                "overall_confidence_score": video.overall_confidence_score,
                "summary": video.summary,
                "analysis_model": video.analysis_model,
            },
            "harmful_events": harmful_events,
            "transcription": transcription,
        }

        if video.safety_report:
            try:
                legacy_report = json.loads(str(video.safety_report))
                safety_report["legacy_report"] = legacy_report
            except json.JSONDecodeError:
                pass

    except Exception as e:
        logger.error(f"Error building analysis results: {str(e)}")
        raise HTTPException(status_code=500, detail="Error building analysis results")

    return AnalysisResult(
        video_id=video_id,
        status="completed",
        safety_report=safety_report,
        created_at=video.uploaded_at,
    )


@router.post("/analyze/{video_id}/retry")
async def retry_analysis(
    video_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Retry failed analysis"""

    account = get_account_by_session_uuid(user_id, db)

    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.account_id == account.id)
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found or access denied")

    if video.analysis_status not in ["failed", "pending"]:
        raise HTTPException(
            status_code=409, detail="Can only retry failed or pending analysis"
        )

    video.analysis_status = "pending"
    db.commit()

    enqueue_analysis(background_tasks, video_id)

    return {
        "video_id": video_id,
        "status": "retry_triggered",
        "message": "Analysis retry has been queued",
    }


@router.post("/upload/url", response_model=URLDownloadResponse)
async def upload_video_from_url(
    request: URLDownloadRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Download video from URL and store for analysis"""

    try:
        if not validators.url(str(request.url)):
            raise HTTPException(status_code=400, detail="Invalid URL format")

        account = get_account_by_session_uuid(user_id, db)

        video_id = str(uuid.uuid4())

        new_video = Video(
            id=video_id,
            account_id=account.id,
            original_filename=f"downloaded_video_{video_id[:8]}.mp4",
            file_size=0,  # Will be updated after download
            file_path=f"./videos/{video_id}/video.mp4",
            analysis_status="pending",
            analysis_model=request.analysis_model,
            source_type="url",
            original_url=str(request.url),
            download_status="pending",
        )

        db.add(new_video)
        db.commit()
        db.refresh(new_video)

        background_tasks.add_task(
            download_video_task,
            video_id=video_id,
            url=str(request.url),
            analysis_model=request.analysis_model,
        )

        return URLDownloadResponse(
            message="Video download started", video_id=video_id, status="downloading"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting video download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/download/{video_id}/status", response_model=DownloadStatusResponse)
async def get_download_status(
    video_id: str,
    user_id: str = Header(..., description="User session UUID from Auth.js"),
    db: Session = Depends(get_db),
):
    """Get download status for a specific video"""

    account = get_account_by_session_uuid(user_id, db)

    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.account_id == account.id)
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    metadata = None
    if video.download_metadata:
        try:
            metadata = json.loads(video.download_metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = None

    return DownloadStatusResponse(
        video_id=video_id,
        download_status=video.download_status,
        analysis_status=video.analysis_status,
        download_error=video.download_error,
        original_url=video.original_url,
        provider=video.download_provider,
        metadata=metadata,
    )


def download_video_task(video_id: str, url: str, analysis_model: str):
    """Background task to download video and trigger analysis"""

    from ..database import SessionLocal

    db = SessionLocal()

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} not found for download")
            return

        video.download_status = "downloading"
        db.commit()

        result = downloader.download_video(url, video_id)

        if result["success"]:
            video.download_status = "completed"
            video.download_provider = result["provider"]
            video.download_metadata = json.dumps(result["metadata"])
            video.file_size = result["metadata"]["file_size"]
            video.original_filename = result["metadata"]["title"] + ".mp4"

            try:
                from ..tools.frame_extraction import extract_frames

                frames_output = extract_frames(
                    video_path=result["file_path"],
                    timestamps=[0],
                    output_dir="frames",
                )
                logger.info(f"Created thumbnail for {video_id}: {frames_output}")
            except Exception as e:
                logger.warning(f"Failed to create thumbnail for {video_id}: {e}")

            metadata_file = UPLOAD_FOLDER / video_id / "metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(result["metadata"], f, indent=2)

            db.commit()

            import asyncio
            from ..services.analysis_pipeline import analyze_video_task

            asyncio.run(analyze_video_task(video_id, result["file_path"], db))

        else:
            video.download_status = "failed"
            video.download_error = result["error"]
            video.analysis_status = "failed"
            db.commit()
            logger.error(f"Failed to download video {video_id}: {result['error']}")

    except Exception as e:
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.download_status = "failed"
                video.download_error = str(e)
                video.analysis_status = "failed"
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status for {video_id}: {db_error}")

        logger.error(f"Error in download task for {video_id}: {str(e)}")
    finally:
        db.close()
