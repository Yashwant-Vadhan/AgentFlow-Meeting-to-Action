"""
Shared data models — Pydantic schemas + SQLAlchemy ORM models.

Pydantic schemas define the JSON contract between pipeline stages.
SQLAlchemy models define the SQLite persistence layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ═══════════════════════════════════════════════
# Pydantic Schemas (JSON contracts between stages)
# ═══════════════════════════════════════════════


class ItemType(str, Enum):
    """Type of extracted item."""
    DECISION = "decision"
    ACTION_ITEM = "action_item"


class VerificationStatus(str, Enum):
    """Status after verification."""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class PipelineStatus(str, Enum):
    """Overall status of an item in the pipeline."""
    EXTRACTED = "extracted"
    VERIFIED = "verified"
    ROUTED = "routed"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


# ── Candidate Item (Extractor Agent output) ───


class CandidateItem(BaseModel):
    """A candidate decision or action item proposed by the Extractor Agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ItemType
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None  # ISO-8601 date string
    source_quote: str
    confidence: float = Field(ge=0.0, le=1.0)


# ── Final Task (cleaned, verified task for routing) ───


class FinalTask(BaseModel):
    """Cleaned task ready for routing to Trello/Calendar/notifications."""
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None  # ISO-8601 date string
    type: ItemType


# ── Verified Item (Verifier Agent output) ─────


class VerifiedItem(BaseModel):
    """Result of the Verifier Agent's assessment of a candidate item."""
    id: str
    status: VerificationStatus
    reason: str
    final_task: Optional[FinalTask] = None  # populated only for approved items


# ── Transcript Segment ────────────────────────


class TranscriptSegment(BaseModel):
    """A single timestamped segment from Whisper transcription."""
    start: float
    end: float
    text: str
    low_confidence: bool = False


# ── API Request/Response Models ───────────────


class SessionCreate(BaseModel):
    """Request body for creating a new session."""
    name: Optional[str] = None


class SessionResponse(BaseModel):
    """Response body for a session."""
    id: str
    name: str
    status: str
    created_at: str
    item_count: int = 0


class ItemStatusUpdate(BaseModel):
    """Request body for approving/rejecting a needs_review item."""
    model_config = {"use_enum_values": True}

    status: VerificationStatus


class WebSocketMessage(BaseModel):
    """Message format for WebSocket broadcasts."""
    type: str  # "transcript_segment", "task_update", "pipeline_status"
    session_id: str
    data: dict


# ═══════════════════════════════════════════════
# SQLAlchemy ORM Models (SQLite persistence)
# ═══════════════════════════════════════════════


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class SessionModel(Base):
    """A processing session (one per uploaded audio file)."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="processing")  # processing | complete | error
    audio_path = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    # Relationships
    transcript_segments = relationship("TranscriptSegmentModel", back_populates="session", cascade="all, delete-orphan")
    task_items = relationship("TaskItemModel", back_populates="session", cascade="all, delete-orphan")


class TranscriptSegmentModel(Base):
    """A single transcript segment, stored in order."""
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    low_confidence = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    session = relationship("SessionModel", back_populates="transcript_segments")


class TaskItemModel(Base):
    """A task item tracked through the pipeline stages."""
    __tablename__ = "task_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)

    # Item content
    type = Column(String, nullable=False)  # "decision" | "action_item"
    description = Column(Text, nullable=False)
    owner = Column(String, nullable=True)
    deadline = Column(String, nullable=True)  # ISO-8601 date string
    source_quote = Column(Text, nullable=False, default="")
    confidence = Column(Float, nullable=False, default=0.0)

    # Pipeline status tracking
    pipeline_status = Column(String, nullable=False, default="extracted")  # PipelineStatus enum value
    verification_status = Column(String, nullable=True)  # VerificationStatus enum value
    verification_reason = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Routing info
    trello_card_id = Column(String, nullable=True)
    trello_card_url = Column(String, nullable=True)
    calendar_event_id = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = relationship("SessionModel", back_populates="task_items")
