from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl


class VideoInfo(BaseModel):
    video_id: str
    original_filename: str
    file_size: int
    upload_timestamp: str
    status: str


class UploadResponse(BaseModel):
    video_id: str
    filename: str
    status: str
    message: str
    path: str


class VideoListResponse(BaseModel):
    videos: List[VideoInfo]
    count: int


class UserVideoResponse(BaseModel):
    video_id: str
    original_filename: str
    file_size: int
    uploaded_at: datetime
    analysis_status: str
    analysis_model: Optional[str] = None
    duration: Optional[int] = None
    safety_rating: Optional[str] = None
    harmful_events_count: Optional[int] = None
    overall_confidence_score: Optional[int] = None
    summary: Optional[str] = None
    thumbnail_url: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AnalysisRequest(BaseModel):
    video_id: str


class AnalysisStatus(BaseModel):
    video_id: str
    status: str
    progress: Optional[int] = 0
    message: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AnalysisResult(BaseModel):
    video_id: str
    status: str
    safety_report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserRegistration(BaseModel):
    id: str  # CUID v2 from OIDC provider
    session_uuid: str  # Auth.js UUID for sessions
    name: str
    email: str
    image: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    image: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class URLDownloadRequest(BaseModel):
    url: HttpUrl
    analysis_model: Optional[str] = "SafeLens/llama-3-8b"


class URLDownloadResponse(BaseModel):
    message: str
    video_id: str
    status: str


class DownloadStatusResponse(BaseModel):
    video_id: str
    download_status: str
    analysis_status: str
    download_error: Optional[str] = None
    original_url: Optional[str] = None
    provider: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
