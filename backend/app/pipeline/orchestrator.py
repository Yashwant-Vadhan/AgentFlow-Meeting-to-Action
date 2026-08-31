"""
orchestrator.py — TY-004: Pipeline orchestrator.

`process_session(session_id)` is the single entry point that drives the full
backend pipeline after a transcript is ready:

  1. Load transcript from SQLite
  2. Call Extractor Agent → candidate items
  3. Call Verifier Agent → verified items
  4. For every approved item → POST to n8n webhook (N8N_WEBHOOK_URL)
  5. After each stage → update item status in SQLite + broadcast over WebSocket

Error handling: each item/stage is wrapped in try/except so one failure
doesn't stop the others.  Failed items show on the dashboard with an error badge.
"""

import logging
from datetime import datetime

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import broadcast
from app.config import settings
from app.models.schema import (
    CandidateItem,
    DBCandidateItem,
    DBSession,
    DBTranscriptSegment,
    DBVerifiedItem,
    VerifiedItem,
)
from app.pipeline import extractor_agent
from app.pipeline import verifier_agent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _broadcast_task_update(session_id: str, item: DBCandidateItem) -> None:
    await broadcast(
        session_id,
        {
            "type": "task_update",
            "data": {
                "id": item.id,
                "session_id": item.session_id,
                "type": item.type,
                "description": item.description,
                "owner": item.owner,
                "deadline": item.deadline,
                "source_quote": item.source_quote,
                "confidence": item.confidence,
                "status": item.status,
                "error_message": item.error_message,
            },
        },
    )


async def _post_to_n8n(verified_item: VerifiedItem) -> bool:
    """
    POST an approved verified item to the n8n webhook.
    Returns True on success, False on failure (caller logs + updates DB).
    """
    if not settings.N8N_WEBHOOK_URL:
        logger.warning("N8N_WEBHOOK_URL is not set; skipping webhook call")
        return False

    payload = {
        "id": verified_item.id,
        "status": verified_item.status,
        "reason": verified_item.reason,
        "final_task": verified_item.final_task.model_dump() if verified_item.final_task else {},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.N8N_WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status < 300:
                    logger.info("n8n webhook OK | item=%s status=%d", verified_item.id, resp.status)
                    return True
                body = await resp.text()
                logger.error(
                    "n8n webhook error | item=%s http=%d body=%s",
                    verified_item.id,
                    resp.status,
                    body[:200],
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
    Full pipeline for one session.  Called as a FastAPI BackgroundTask after
    the transcript is ready.

    Args:
        session_id: UUID string of the session to process.
        db:         Async SQLAlchemy session (injected by the caller).
    """
    logger.info("Orchestrator started | session=%s", session_id)

    # ── 0. Load session + transcript ─────────────────────────────────────────
    session_row = await db.get(DBSession, session_id)
    if not session_row:
        logger.error("Session not found | session=%s", session_id)
        return

    segments_result = await db.execute(
        select(DBTranscriptSegment)
        .where(DBTranscriptSegment.session_id == session_id)
        .order_by(DBTranscriptSegment.start)
    )
    segments = segments_result.scalars().all()
    transcript = " ".join(seg.text for seg in segments)

    if not transcript.strip():
        logger.warning("Empty transcript | session=%s — nothing to extract", session_id)
        await broadcast(session_id, {"type": "pipeline_status", "stage": "extractor", "status": "skipped", "message": "No transcript text found"})
        return

    meeting_date: str | None = session_row.meeting_date

    # ── 1. Extraction stage ───────────────────────────────────────────────────
    await broadcast(session_id, {"type": "pipeline_status", "stage": "extractor", "status": "running"})
    candidate_items: list[CandidateItem] = []
    try:
        candidate_items = await extractor_agent.extract(transcript, meeting_date)
        logger.info("Extracted %d candidate items | session=%s", len(candidate_items), session_id)
    except Exception as exc:
        logger.error("Extractor failed | session=%s error=%s", session_id, exc, exc_info=True)
        await broadcast(session_id, {"type": "pipeline_status", "stage": "extractor", "status": "error", "message": str(exc)})
        # Update session status but continue — show partial results
        session_row.status = "error"
        await db.commit()
        return

    # Persist candidates to DB + broadcast each one
    db_candidates: list[DBCandidateItem] = []
    for item in candidate_items:
        db_item = DBCandidateItem(
            id=item.id,
            session_id=session_id,
            type=item.type,
            description=item.description,
            owner=item.owner,
            deadline=item.deadline,
            source_quote=item.source_quote,
            confidence=item.confidence,
            status="extracted",
        )
        db.add(db_item)
        db_candidates.append(db_item)

    await db.commit()
    for db_item in db_candidates:
        await _broadcast_task_update(session_id, db_item)

    await broadcast(session_id, {"type": "pipeline_status", "stage": "extractor", "status": "done", "message": f"{len(candidate_items)} items extracted"})

    # ── 2. Verification stage ─────────────────────────────────────────────────
    await broadcast(session_id, {"type": "pipeline_status", "stage": "verifier", "status": "running"})

    try:
        verified_items = verifier_agent.verify(candidate_items, transcript)
        logger.info("Verified %d items | session=%s", len(verified_items), session_id)
    except Exception as exc:
        logger.error("Verifier failed | session=%s error=%s", session_id, exc, exc_info=True)
        # Mark all extracted items as needs_review so dashboard doesn't hang
        for db_item in db_candidates:
            db_item.status = "needs_review"
            db_item.error_message = f"Verifier error: {exc}"
        await db.commit()
        for db_item in db_candidates:
            await _broadcast_task_update(session_id, db_item)
        await broadcast(session_id, {"type": "pipeline_status", "stage": "verifier", "status": "error", "message": str(exc)})
        return

    # Update DB with verified status
    for v_item in verified_items:
        # Update the candidate item's status
        candidate_db = next((c for c in db_candidates if c.id == v_item.id), None)
        if candidate_db:
            candidate_db.status = v_item.status  # approved | rejected | needs_review

        # Persist verified item record
        final = v_item.final_task
        db_verified = DBVerifiedItem(
            candidate_id=v_item.id,
            session_id=session_id,
            status=v_item.status,
            reason=v_item.reason,
            final_description=final.description if final else None,
            final_owner=final.owner if final else None,
            final_deadline=final.deadline if final else None,
            final_type=final.type if final else None,
        )
        db.add(db_verified)

    await db.commit()
    for db_item in db_candidates:
        await _broadcast_task_update(session_id, db_item)

    await broadcast(session_id, {"type": "pipeline_status", "stage": "verifier", "status": "done"})

    # ── 3. Routing stage: POST approved items to n8n ───────────────────────────
    await broadcast(session_id, {"type": "pipeline_status", "stage": "router", "status": "running"})
    approved_count = 0

    for v_item in verified_items:
        if v_item.status != "approved":
            continue

        candidate_db = next((c for c in db_candidates if c.id == v_item.id), None)

        try:
            success = await _post_to_n8n(v_item)
            if success:
                approved_count += 1
                if candidate_db:
                    candidate_db.status = "routed"
                    await db.commit()
                    await _broadcast_task_update(session_id, candidate_db)
            else:
                if candidate_db:
                    candidate_db.status = "failed"
                    candidate_db.error_message = "n8n webhook call failed"
                    await db.commit()
                    await _broadcast_task_update(session_id, candidate_db)
        except Exception as exc:
            logger.error("Routing failed | item=%s session=%s error=%s", v_item.id, session_id, exc, exc_info=True)
            if candidate_db:
                candidate_db.status = "failed"
                candidate_db.error_message = str(exc)
                await db.commit()
                await _broadcast_task_update(session_id, candidate_db)

    # ── 4. Final session status ───────────────────────────────────────────────
    session_row.status = "complete"
    await db.commit()
    await broadcast(session_id, {
        "type": "pipeline_status",
        "stage": "router",
        "status": "done",
        "message": f"{approved_count} items routed to n8n",
    })
    logger.info("Orchestrator complete | session=%s routed=%d", session_id, approved_count)
