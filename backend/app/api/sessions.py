"""
Session API endpoints — upload, status, and approve/reject.

Endpoints:
- POST   /api/v1/sessions                              — upload audio + create session
- GET    /api/v1/sessions/{session_id}                  — get session status + items
- GET    /api/v1/sessions                               — list all sessions
- PATCH  /api/v1/sessions/{session_id}/items/{item_id}  — approve/reject a needs_review item
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import broadcast
from app.config import get_settings
from app.models.schema import (
    FinalTask,
    ItemStatusUpdate,
    ItemType,
    PipelineStatus,
    SessionModel,
    SessionResponse,
    TaskItemModel,
    TranscriptSegmentModel,
    VerificationStatus,
)
from app.pipeline.audio_preprocess import chunk_audio, preprocess_audio
from app.pipeline.orchestrator import process_session
from app.pipeline.transcribe import transcribe_chunk

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Dependency: DB session ────────────────────
async def get_db():
    """Get an async DB session — imported from main to avoid circular imports."""
    from app.main import async_session
    async with async_session() as session:
        yield session


# ── Background Pipeline Task ──────────────────
async def run_audio_pipeline(session_id: str, audio_path: str):
    """
    Background pipeline worker for a session:
    1. Preprocesses audio (volume normalization / noise reduction)
    2. Chunks audio into ~30-60s segments
    3. Transcribes each chunk using Whisper & broadcasts transcript segments over WS
    4. Persists transcript segments to SQLite
    5. Triggers orchestrator (Extractor -> Verifier -> n8n routing)
    """
    from app.main import async_session

    logger.info(f"Starting background audio pipeline for session {session_id}")
    try:
        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "preprocess",
            "status": "running",
            "message": "Preprocessing audio...",
        })

        # 1. Preprocess
        cleaned_path = preprocess_audio(audio_path)

        # 2. Chunking
        chunks = chunk_audio(cleaned_path)
        logger.info(f"Session {session_id}: {len(chunks)} chunk(s) to transcribe")

        # 3. Transcribe & stream
        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "transcribe",
            "status": "running",
            "message": "Transcribing audio with Whisper...",
        })

        async with async_session() as db:
            for chunk_file in chunks:
                segments = transcribe_chunk(chunk_file)
                for seg in segments:
                    # Save DB segment
                    db_seg = TranscriptSegmentModel(
                        session_id=session_id,
                        start_time=seg["start"],
                        end_time=seg["end"],
                        text=seg["text"],
                        low_confidence=seg.get("low_confidence", False),
                    )
                    db.add(db_seg)

                    # Broadcast WS message
                    await broadcast(session_id, {
                        "type": "transcript_segment",
                        "session_id": session_id,
                        "data": seg,
                    })

            await db.commit()

        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "transcribe",
            "status": "done",
            "message": "Transcription complete",
        })

        # 4. Trigger Extractor -> Verifier -> Routing
        async with async_session() as db:
            await process_session(session_id, db)

    except Exception as e:
        logger.error(f"Background pipeline failed for session {session_id}: {e}", exc_info=True)
        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "pipeline",
            "status": "error",
            "message": str(e),
        })

        async with async_session() as db:
            session = await db.get(SessionModel, session_id)
            if session:
                session.status = "error"
                session.error_message = str(e)
                await db.commit()


# ═══════════════════════════════════════════════
# POST /api/v1/sessions — Upload audio & create session
# ═══════════════════════════════════════════════


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a meeting audio file and create a new processing session.

    Accepts .mp3, .wav, .m4a files up to 200MB.
    Returns the created session info; processing starts in the background.
    """
    settings = get_settings()

    # ── Validate file type (supports audio and video) ──
    allowed_types = {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".mkv", ".webm"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_types)}",
        )

    # ── Validate file size ──
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(content) / (1024*1024):.1f}MB). Max: {settings.max_upload_size_mb}MB.",
        )

    # ── Save file to disk ──
    session_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    audio_path = upload_dir / f"{session_id}{ext}"

    with open(audio_path, "wb") as f:
        f.write(content)

    # ── Create session record ──
    session_name = name or f"Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    session = SessionModel(
        id=session_id,
        name=session_name,
        status="processing",
        audio_path=str(audio_path),
    )
    db.add(session)
    await db.commit()

    logger.info(f"Session created: {session_id} ({session_name}), file: {audio_path}")

    # Trigger background pipeline
    background_tasks.add_task(run_audio_pipeline, session_id, str(audio_path))

    return SessionResponse(
        id=session_id,
        name=session_name,
        status="processing",
        created_at=session.created_at.isoformat(),
        item_count=0,
    )


# ═══════════════════════════════════════════════
# GET /api/v1/sessions — List all sessions
# ═══════════════════════════════════════════════


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all sessions, newest first, with basic pagination."""
    result = await db.execute(
        select(SessionModel)
        .order_by(SessionModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()

    responses = []
    for s in sessions:
        # Count task items for this session
        item_result = await db.execute(
            select(TaskItemModel).where(TaskItemModel.session_id == s.id)
        )
        item_count = len(item_result.scalars().all())

        responses.append(
            SessionResponse(
                id=s.id,
                name=s.name,
                status=s.status,
                created_at=s.created_at.isoformat(),
                item_count=item_count,
            )
        )

    return responses


# ═══════════════════════════════════════════════
# GET /api/v1/sessions/{session_id} — Get session details
# ═══════════════════════════════════════════════


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full session details including all task items."""
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Get all transcript segments
    segments_result = await db.execute(
        select(TranscriptSegmentModel)
        .where(TranscriptSegmentModel.session_id == session_id)
        .order_by(TranscriptSegmentModel.start_time)
    )
    segments = segments_result.scalars().all()

    # Get all task items
    items_result = await db.execute(
        select(TaskItemModel)
        .where(TaskItemModel.session_id == session_id)
        .order_by(TaskItemModel.created_at)
    )
    items = items_result.scalars().all()

    return {
        "id": session.id,
        "name": session.name,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "error_message": session.error_message,
        "transcript_segments": [
            {
                "start": seg.start_time,
                "end": seg.end_time,
                "text": seg.text,
                "low_confidence": seg.low_confidence,
            }
            for seg in segments
        ],
        "items": [
            {
                "id": item.id,
                "type": item.type,
                "description": item.description,
                "owner": item.owner,
                "deadline": item.deadline,
                "source_quote": item.source_quote,
                "confidence": item.confidence,
                "pipeline_status": item.pipeline_status,
                "verification_status": item.verification_status,
                "verification_reason": item.verification_reason,
                "trello_card_url": item.trello_card_url,
                "error_message": item.error_message,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
    }


# ═══════════════════════════════════════════════
# PATCH /api/v1/sessions/{session_id}/items/{item_id} — Approve/Reject
# ═══════════════════════════════════════════════


@router.patch("/sessions/{session_id}/items/{item_id}")
async def update_item_status(
    session_id: str,
    item_id: str,
    body: ItemStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or reject a needs_review item from the dashboard.

    - If approved: routes the item through n8n (same as auto-approved items)
      and updates status to 'routed'.
    - If rejected: updates status to 'rejected'.

    Both cases broadcast the update over WebSocket.
    """
    settings = get_settings()

    # ── Fetch the item ──
    result = await db.execute(
        select(TaskItemModel).where(
            TaskItemModel.id == item_id,
            TaskItemModel.session_id == session_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Item {item_id} not found in session {session_id}",
        )

    if item.pipeline_status != PipelineStatus.NEEDS_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Item is '{item.pipeline_status}', not 'needs_review'. Only needs_review items can be manually updated.",
        )

    # ── Handle approval ──
    if body.status == VerificationStatus.APPROVED:
        # Route through n8n — same path as auto-approved items
        final_task = {
            "id": item.id,
            "description": item.description,
            "owner": item.owner or "Unassigned",
            "deadline": item.deadline,
            "type": item.type,
        }

        routed = await _route_to_n8n(final_task, settings)

        if routed:
            item.pipeline_status = PipelineStatus.ROUTED.value
            item.verification_status = VerificationStatus.APPROVED.value
            item.verification_reason = "Manually approved via dashboard"
        else:
            item.pipeline_status = PipelineStatus.FAILED.value
            item.verification_status = VerificationStatus.APPROVED.value
            item.verification_reason = "Manually approved, but routing to n8n failed"
            item.error_message = "Failed to route to n8n webhook"

    # ── Handle rejection ──
    elif body.status == VerificationStatus.REJECTED:
        item.pipeline_status = PipelineStatus.REJECTED.value
        item.verification_status = VerificationStatus.REJECTED.value
        item.verification_reason = "Manually rejected via dashboard"

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be 'approved' or 'rejected'.",
        )

    await db.commit()

    # ── Broadcast update via WebSocket ──
    try:
        from app.api.websocket import broadcast
        await broadcast(session_id, {
            "type": "task_update",
            "session_id": session_id,
            "data": {
                "id": item.id,
                "pipeline_status": item.pipeline_status,
                "verification_status": item.verification_status,
                "verification_reason": item.verification_reason,
                "description": item.description,
                "owner": item.owner,
                "deadline": item.deadline,
            },
        })
    except Exception as e:
        logger.warning(f"Failed to broadcast WebSocket update: {e}")

    logger.info(
        f"Item {item_id} in session {session_id} updated: "
        f"status={item.pipeline_status}, verification={item.verification_status}"
    )

    return {
        "id": item.id,
        "pipeline_status": item.pipeline_status,
        "verification_status": item.verification_status,
        "verification_reason": item.verification_reason,
    }


# ═══════════════════════════════════════════════
# Helper: Route task to n8n webhook
# ═══════════════════════════════════════════════


async def _route_to_n8n(final_task: dict, settings=None) -> bool:
    """
    POST a verified task to the n8n webhook.

    Returns True on success, False on failure (logs the error).
    """
    if settings is None:
        settings = get_settings()

    webhook_url = settings.n8n_webhook_url
    if not webhook_url:
        logger.warning("N8N_WEBHOOK_URL not configured — skipping routing")
        return False

    payload = {
        "status": "approved",
        "reason": "Auto-approved or manually approved",
        "final_task": final_task,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()

        logger.info(f"Successfully routed task {final_task.get('id')} to n8n")
        return True

    except httpx.HTTPStatusError as e:
        logger.error(
            f"n8n webhook returned {e.response.status_code}: {e.response.text[:200]}"
        )
        return False
    except httpx.ConnectError as e:
        logger.error(f"Cannot reach n8n webhook at {webhook_url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error routing to n8n: {e}")
        return False
