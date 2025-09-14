from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    Text,
    ForeignKey,
    Integer,
    Float,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, index=True)  # CUID v2 from OIDC
    session_uuid = Column(
        String, unique=True, index=True, nullable=True
    )  # Auth.js UUID for sessions
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    image = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    videos = relationship("Video", back_populates="account")


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(
        String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    analysis_status = Column(String, default="pending")
    analysis_model = Column(String, nullable=True)
    safety_report = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)

    safety_rating = Column(String(20), nullable=True)
    harmful_events_count = Column(Integer, default=0)
    overall_confidence_score = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)

    source_type = Column(String, default="upload")
    original_url = Column(Text, nullable=True)
    download_provider = Column(String, nullable=True)
    download_status = Column(String, default="pending")
    download_metadata = Column(Text, nullable=True)
    download_error = Column(Text, nullable=True)

    account = relationship("Account", back_populates="videos")
    harmful_events = relationship("HarmfulEvent", back_populates="video")
    transcription = relationship("Transcription", back_populates="video", uselist=False)
    analysis_runs = relationship("AnalysisRun", back_populates="video")


class HarmfulEvent(Base):
    __tablename__ = "harmful_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(
        String, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    timestamp = Column(Float, nullable=False)
    categories = Column(Text, nullable=True)
    verification_source = Column(String(50), nullable=True)
    explanation = Column(Text, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    severity = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)
    analysis_performed = Column(Text, nullable=True)
    planning_mode = Column(String(50), nullable=True)
    report_version = Column(Integer, nullable=True)
    analysis_run_id = Column(
        String, ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )

    video = relationship("Video", back_populates="harmful_events")
    visual_evidence = relationship("VisualEvidence", back_populates="harmful_event")
    audio_evidence = relationship("AudioEvidence", back_populates="harmful_event")
    analysis_run = relationship("AnalysisRun", back_populates="harmful_events")


class VisualEvidence(Base):
    __tablename__ = "visual_evidence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    harmful_event_id = Column(
        String, ForeignKey("harmful_events.id", ondelete="CASCADE"), nullable=False
    )
    ocr_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    harmful_event = relationship("HarmfulEvent", back_populates="visual_evidence")
    image_labels = relationship("ImageLabel", back_populates="visual_evidence")


class ImageLabel(Base):
    __tablename__ = "image_labels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    visual_evidence_id = Column(
        String, ForeignKey("visual_evidence.id", ondelete="CASCADE"), nullable=False
    )
    label = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    visual_evidence = relationship("VisualEvidence", back_populates="image_labels")


class AudioEvidence(Base):
    __tablename__ = "audio_evidence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    harmful_event_id = Column(
        String, ForeignKey("harmful_events.id", ondelete="CASCADE"), nullable=False
    )
    transcript_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    harmful_event = relationship("HarmfulEvent", back_populates="audio_evidence")


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(
        String, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    full_text = Column(Text, nullable=True)
    word_timestamps = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="transcription")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(
        String, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False, default="pending")
    stage = Column(String, nullable=True)
    model_used = Column(String, nullable=True)
    planning_mode = Column(String, nullable=True)
    segments_count = Column(Integer, nullable=True)
    frames_analyzed = Column(Integer, nullable=True)
    tokens_prompt = Column(Integer, nullable=True)
    tokens_completion = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    run_metadata = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    video = relationship("Video", back_populates="analysis_runs")
    harmful_events = relationship("HarmfulEvent", back_populates="analysis_run")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
