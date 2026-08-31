"""
Unit tests for Sessions API endpoints (including PATCH approve/reject).
"""

import pytest
from app.models.schema import ItemStatusUpdate, VerificationStatus


def test_item_status_update_model():
    """Verify ItemStatusUpdate model parses valid status inputs."""
    update_approved = ItemStatusUpdate(status=VerificationStatus.APPROVED)
    assert update_approved.status == VerificationStatus.APPROVED

    update_rejected = ItemStatusUpdate(status=VerificationStatus.REJECTED)
    assert update_rejected.status == VerificationStatus.REJECTED
