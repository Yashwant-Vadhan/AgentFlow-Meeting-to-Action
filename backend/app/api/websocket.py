"""
WebSocket connection manager — pushes live updates to connected dashboard clients.

Provides:
- /ws/sessions/{session_id} endpoint for per-session connections
- broadcast(session_id, message) for other modules to push updates
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════
# Connection Manager (in-memory)
# ═══════════════════════════════════════════════


class ConnectionManager:
    """
    Manages WebSocket connections per session.

    Uses a simple dict of session_id → list[WebSocket].
    Sufficient for single-instance MVP; not distributed-safe.
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept a WebSocket connection and register it for a session."""
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)
        logger.info(
            f"WebSocket connected for session {session_id} "
            f"(total: {len(self._connections[session_id])})"
        )

    def disconnect(self, session_id: str, websocket: WebSocket):
        """Remove a WebSocket connection from a session."""
        if session_id in self._connections:
            try:
                self._connections[session_id].remove(websocket)
            except ValueError:
                pass
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info(f"WebSocket disconnected for session {session_id}")

    async def broadcast(self, session_id: str, message: dict[str, Any]):
        """
        Send a JSON message to all WebSocket clients connected to a session.

        Silently removes any broken connections.
        """
        if session_id not in self._connections:
            return

        broken: list[WebSocket] = []
        data = json.dumps(message)

        for ws in self._connections[session_id]:
            try:
                await ws.send_text(data)
            except Exception:
                broken.append(ws)

        # Clean up broken connections
        for ws in broken:
            self.disconnect(session_id, ws)

        if self._connections.get(session_id):
            logger.debug(
                f"Broadcast to {len(self._connections[session_id])} clients "
                f"for session {session_id}"
            )

    def get_connection_count(self, session_id: str) -> int:
        """Return the number of active connections for a session."""
        return len(self._connections.get(session_id, []))


# ── Module-level singleton ────────────────────
manager = ConnectionManager()


async def broadcast(session_id: str, message: dict[str, Any]):
    """
    Convenience function for other modules to broadcast messages.

    Usage:
        from app.api.websocket import broadcast
        await broadcast(session_id, {"type": "task_update", "data": {...}})
    """
    await manager.broadcast(session_id, message)


# ═══════════════════════════════════════════════
# WebSocket Endpoint
# ═══════════════════════════════════════════════


@router.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Per-session WebSocket endpoint.

    Clients connect here to receive live updates:
    - transcript_segment: new transcript lines as they're transcribed
    - task_update: candidate/verified item status changes
    - pipeline_status: overall session status changes
    """
    await manager.connect(session_id, websocket)
    try:
        while True:
            # Keep the connection alive — listen for any client messages
            # (e.g., heartbeats). We don't currently process client messages
            # but this keeps the connection from closing.
            data = await websocket.receive_text()
            # Could handle client-sent messages here if needed in the future
            logger.debug(f"Received from client (session {session_id}): {data}")
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(session_id, websocket)
