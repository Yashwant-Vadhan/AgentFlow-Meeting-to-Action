"""
orchestrator.py — Pipeline orchestrator.

`process_session(session_id, db)` is the single entry point that drives the full
backend pipeline after a transcript is ready:

  1. Load transcript segments from SQLite
  2. Call Extractor Agent -> candidate items
  3. Call Verifier Agent -> verified items
  4. For every approved item -> POST to n8n webhook
  5. After each stage -> update item status in SQLite + broadcast over WebSocket
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import broadcast
from app.config import get_settings
from app.models.schema import (
    CandidateItem,
    PipelineStatus,
    SessionModel,
    TaskItemModel,
    TranscriptSegmentModel,
    VerificationStatus,
    VerifiedItem,
)
from app.pipeline import extractor_agent
from app.pipeline import verifier_agent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _broadcast_task_update(session_id: str, item: TaskItemModel) -> None:
    await broadcast(
        session_id,
        {
            "type": "task_update",
            "session_id": session_id,
            "data": {
                "id": item.id,
                "pipeline_status": item.pipeline_status,
                "verification_status": item.verification_status,
                "verification_reason": item.verification_reason,
                "type": item.type,
                "description": item.description,
                "owner": item.owner,
                "deadline": item.deadline,
                "source_quote": item.source_quote,
                "confidence": item.confidence,
                "trello_card_url": item.trello_card_url,
                "error_message": item.error_message,
            },
        },
    )


async def _post_to_n8n(verified_item: VerifiedItem) -> bool:
    """
    POST an approved verified item to the n8n webhook.
    Returns True on success, False on failure (caller logs + updates DB).
    """
    settings = get_settings()
    if not settings.n8n_webhook_url:
        logger.warning("N8N_WEBHOOK_URL is not set; skipping webhook call")
        return False

    payload = {
        "id": verified_item.id,
        "status": verified_item.status.value if hasattr(verified_item.status, "value") else str(verified_item.status),
        "reason": verified_item.reason,
        "final_task": verified_item.final_task.model_dump() if verified_item.final_task else {},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.n8n_webhook_url, json=payload)
            if resp.status_code < 300:
                logger.info("n8n webhook OK | item=%s status=%d", verified_item.id, resp.status_code)
                return True
            logger.error(
                "n8n webhook error | item=%s http=%d body=%s",
                verified_item.id,
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as exc:
        logger.error("n8n webhook call failed | item=%s error=%s", verified_item.id, exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def process_session(session_id: str, db: AsyncSession) -> None:
    """
    Full pipeline for one session. Called after transcription is complete.

    Args:
        session_id: UUID string of the session to process.
        db:         Async SQLAlchemy session.
    """
    logger.info("Orchestrator started | session=%s", session_id)

    # ── 0. Load session + transcript ─────────────────────────────────────────
    session_row = await db.get(SessionModel, session_id)
    if not session_row:
        logger.error("Session not found | session=%s", session_id)
        return

    segments_result = await db.execute(
        select(TranscriptSegmentModel)
        .where(TranscriptSegmentModel.session_id == session_id)
        .order_by(TranscriptSegmentModel.start_time)
    )
    segments = segments_result.scalars().all()
    transcript = " ".join(seg.text for seg in segments)

    if not transcript.strip():
        logger.warning("Empty transcript | session=%s — nothing to extract", session_id)
        session_row.status = "complete"
        await db.commit()
        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "extractor",
            "status": "skipped",
            "message": "No transcript text found",
        })
        return

    # ── 1. Extraction stage ───────────────────────────────────────────────────
    await broadcast(session_id, {"type": "pipeline_status", "stage": "extractor", "status": "running"})
    candidate_items: list[CandidateItem] = []
    try:
        candidate_items = await extractor_agent.extract(transcript)
        logger.info("Extracted %d candidate items | session=%s", len(candidate_items), session_id)
    except Exception as exc:
        logger.error("Extractor failed | session=%s error=%s", session_id, exc, exc_info=True)
        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "extractor",
            "status": "error",
            "message": str(exc),
        })
        session_row.status = "error"
        session_row.error_message = f"Extractor failed: {exc}"
        await db.commit()
        return

    # Persist candidates to DB as TaskItemModel + broadcast each one
    db_items: dict[str, TaskItemModel] = {}
    for item in candidate_items:
        db_item = TaskItemModel(
            id=item.id,
            session_id=session_id,
            type=item.type.value if hasattr(item.type, "value") else str(item.type),
            description=item.description,
            owner=item.owner,
            deadline=item.deadline,
            source_quote=item.source_quote,
            confidence=item.confidence,
            pipeline_status=PipelineStatus.EXTRACTED.value,
        )
        db.add(db_item)
        db_items[item.id] = db_item

    await db.commit()
    for db_item in db_items.values():
        await _broadcast_task_update(session_id, db_item)

    await broadcast(session_id, {
        "type": "pipeline_status",
        "stage": "extractor",
        "status": "done",
        "message": f"{len(candidate_items)} items extracted",
    })

    # ── 2. Verification stage ─────────────────────────────────────────────────
    await broadcast(session_id, {"type": "pipeline_status", "stage": "verifier", "status": "running"})

    try:
        verified_items: list[VerifiedItem] = await verifier_agent.verify(candidate_items, transcript)
        logger.info("Verified %d items | session=%s", len(verified_items), session_id)
    except Exception as exc:
        logger.error("Verifier failed | session=%s error=%s", session_id, exc, exc_info=True)
        # Mark all extracted items as needs_review so dashboard doesn't hang
        for db_item in db_items.values():
            db_item.pipeline_status = PipelineStatus.NEEDS_REVIEW.value
            db_item.error_message = f"Verifier error: {exc}"
        await db.commit()
        for db_item in db_items.values():
            await _broadcast_task_update(session_id, db_item)
        await broadcast(session_id, {
            "type": "pipeline_status",
            "stage": "verifier",
            "status": "error",
            "message": str(exc),
        })
        return

    # Update DB with verified status
    for v_item in verified_items:
        db_item = db_items.get(v_item.id)
        if not db_item:
            continue

        status_val = v_item.status.value if hasattr(v_item.status, "value") else str(v_item.status)
        db_item.verification_status = status_val
        db_item.verification_reason = v_item.reason

        if v_item.final_task:
            db_item.description = v_item.final_task.description
            db_item.owner = v_item.final_task.owner
            db_item.deadline = v_item.final_task.deadline
            if v_item.final_task.type:
                db_item.type = v_item.final_task.type.value if hasattr(v_item.final_task.type, "value") else str(v_item.final_task.type)

        if v_item.status == VerificationStatus.APPROVED:
            db_item.pipeline_status = PipelineStatus.VERIFIED.value
        elif v_item.status == VerificationStatus.REJECTED:
            db_item.pipeline_status = PipelineStatus.REJECTED.value
        else:
            db_item.pipeline_status = PipelineStatus.NEEDS_REVIEW.value

    # Guard: Ensure no candidate items remain stranded in 'extracted' status
    for db_item in db_items.values():
        if db_item.pipeline_status == PipelineStatus.EXTRACTED.value:
            db_item.pipeline_status = PipelineStatus.NEEDS_REVIEW.value
            db_item.verification_status = VerificationStatus.NEEDS_REVIEW.value
            db_item.verification_reason = "Unverified candidate: marked for manual review"

    await db.commit()
    for db_item in db_items.values():
        await _broadcast_task_update(session_id, db_item)

    await broadcast(session_id, {"type": "pipeline_status", "stage": "verifier", "status": "done"})

    # ── 3. Routing stage: POST approved items to n8n ───────────────────────────
    await broadcast(session_id, {"type": "pipeline_status", "stage": "router", "status": "running"})
    approved_count = 0

    for v_item in verified_items:
        if v_item.status != VerificationStatus.APPROVED:
            continue

        db_item = db_items.get(v_item.id)

        try:
            success = await _post_to_n8n(v_item)
            if success:
                approved_count += 1
                if db_item:
                    db_item.pipeline_status = PipelineStatus.ROUTED.value
                    await db.commit()
                    await _broadcast_task_update(session_id, db_item)
            else:
                if db_item:
                    db_item.pipeline_status = PipelineStatus.FAILED.value
                    db_item.error_message = "n8n webhook call failed or not configured"
                    await db.commit()
                    await _broadcast_task_update(session_id, db_item)
        except Exception as exc:
            logger.error("Routing failed | item=%s session=%s error=%s", v_item.id, session_id, exc, exc_info=True)
            if db_item:
                db_item.pipeline_status = PipelineStatus.FAILED.value
                db_item.error_message = str(exc)
                await db.commit()
                await _broadcast_task_update(session_id, db_item)

    # ── 4. Final session status ───────────────────────────────────────────────
    session_row.status = "complete"
    await db.commit()
    await broadcast(session_id, {
        "type": "pipeline_status",
        "stage": "router",
        "status": "done",
        "message": f"{approved_count} item(s) routed to n8n",
    })
    logger.info("Orchestrator complete | session=%s routed=%d", session_id, approved_count)
