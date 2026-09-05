"""
Unit tests for Sessions API endpoints (including DELETE and PATCH approve/reject).
"""

import pytest
import httpx
from app.main import app
from app.models.schema import ItemStatusUpdate, VerificationStatus


def test_item_status_update_model():
    """Verify ItemStatusUpdate model parses valid status inputs."""
    update_approved = ItemStatusUpdate(status=VerificationStatus.APPROVED)
    assert update_approved.status == VerificationStatus.APPROVED

    update_rejected = ItemStatusUpdate(status=VerificationStatus.REJECTED)
    assert update_rejected.status == VerificationStatus.REJECTED


@pytest.mark.asyncio
async def test_get_nonexistent_session():
    """Verify GET on a non-existent session returns 404."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/non-existent-session-id")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_session():
    """Verify DELETE on a non-existent session returns 404."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v1/sessions/non-existent-session-id")
        assert response.status_code == 404
