"""
Tests for the Verifier Agent module.

Covers:
- TS-001: Grounding cross-check (approve valid, reject hypothetical, reject incomplete)
- TS-002: Duplicate detection (merge similar items)
- Error handling: LLM failure → needs_review fallback
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models.schema import CandidateItem, ItemType, VerificationStatus
from app.pipeline.verifier_agent import verify, deduplicate, _merge_items


# ═══════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════

SAMPLE_TRANSCRIPT = """
Alice: Alright, let's go over the action items from today's meeting.

Bob: I'll send the design document to the team by Friday. I've already started drafting it.

Alice: Great. And Carol, can you review the budget proposal?

Carol: Sure, I'll have the budget review done by next Wednesday.

Dave: What if we also looked into the new vendor options? Just a thought.

Alice: Let's hold off on that for now and revisit next quarter.

Bob: Should we schedule a follow-up meeting for next week?

Alice: Yes, let's do that. Bob, can you set that up?

Bob: Will do. I'll send the calendar invite by end of day.
"""


def _make_candidate(
    description: str,
    source_quote: str,
    owner: str | None = None,
    deadline: str | None = None,
    confidence: float = 0.85,
    item_id: str | None = None,
) -> CandidateItem:
    """Helper to create a CandidateItem for testing."""
    return CandidateItem(
        id=item_id or f"test-{hash(description) % 10000}",
        type=ItemType.ACTION_ITEM,
        description=description,
        owner=owner,
        deadline=deadline,
        source_quote=source_quote,
        confidence=confidence,
    )


# ═══════════════════════════════════════════════
# TS-001: Grounding Cross-Check Tests
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_approve_valid_grounded_item():
    """A well-formed, clearly grounded candidate item should be approved."""
    candidate = _make_candidate(
        description="Send the design document to the team by Friday",
        source_quote="I'll send the design document to the team by Friday",
        owner="Bob",
        deadline="2026-09-05",
    )

    # Mock the LLM to return an approval
    mock_response = {
        "status": "approved",
        "reason": "Source quote is verbatim in the transcript and represents a clear commitment by Bob.",
        "corrected_description": None,
        "corrected_owner": None,
        "corrected_deadline": None,
    }

    with patch("app.pipeline.verifier_agent.call_llm_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        results = await verify([candidate], SAMPLE_TRANSCRIPT)

    assert len(results) == 1
    result = results[0]
    assert result.status == VerificationStatus.APPROVED
    assert result.final_task is not None
    assert result.final_task.owner == "Bob"
    assert result.final_task.deadline == "2026-09-05"


@pytest.mark.asyncio
async def test_reject_hypothetical_misread_as_decision():
    """A hypothetical statement should be rejected — not treated as a commitment."""
    candidate = _make_candidate(
        description="Look into the new vendor options",
        source_quote="What if we also looked into the new vendor options? Just a thought.",
        owner="Dave",
        deadline=None,
    )

    mock_response = {
        "status": "rejected",
        "reason": "The source quote is a hypothetical suggestion ('What if we...'), not a commitment. It was also explicitly deferred by Alice.",
        "corrected_description": None,
        "corrected_owner": None,
        "corrected_deadline": None,
    }

    with patch("app.pipeline.verifier_agent.call_llm_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        results = await verify([candidate], SAMPLE_TRANSCRIPT)

    assert len(results) == 1
    result = results[0]
    assert result.status == VerificationStatus.REJECTED
    assert "hypothetical" in result.reason.lower() or "suggestion" in result.reason.lower()
    assert result.final_task is None


@pytest.mark.asyncio
async def test_reject_item_missing_both_owner_and_deadline():
    """An item missing BOTH owner AND deadline should be auto-rejected without LLM call."""
    candidate = _make_candidate(
        description="Review the meeting notes",
        source_quote="Let's review the meeting notes.",
        owner=None,
        deadline=None,
    )

    # The LLM should NOT be called — this is an auto-reject
    with patch("app.pipeline.verifier_agent.call_llm_json", new_callable=AsyncMock) as mock_llm:
        results = await verify([candidate], SAMPLE_TRANSCRIPT)
        mock_llm.assert_not_called()

    assert len(results) == 1
    result = results[0]
    assert result.status == VerificationStatus.REJECTED
    assert "owner" in result.reason.lower() and "deadline" in result.reason.lower()


@pytest.mark.asyncio
async def test_empty_candidate_list_returns_empty():
    """Verifying an empty list should return an empty list without errors."""
    results = await verify([], SAMPLE_TRANSCRIPT)
    assert results == []


@pytest.mark.asyncio
async def test_llm_failure_marks_needs_review():
    """If the LLM call fails, the item should be marked needs_review, not crash."""
    candidate = _make_candidate(
        description="Send calendar invite by end of day",
        source_quote="I'll send the calendar invite by end of day.",
        owner="Bob",
        deadline=None,
    )

    with patch("app.pipeline.verifier_agent.call_llm_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("Ollama connection refused")
        results = await verify([candidate], SAMPLE_TRANSCRIPT)

    assert len(results) == 1
    result = results[0]
    assert result.status == VerificationStatus.NEEDS_REVIEW
    assert result.final_task is not None  # still populates final_task for manual review
    assert "error" in result.reason.lower()


# ═══════════════════════════════════════════════
# TS-002: Duplicate Detection Tests
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_duplicate_items_merge_into_one():
    """Two candidate items describing the same task should merge into one."""
    item_a = _make_candidate(
        description="Bob will send the design document to the team by Friday",
        source_quote="I'll send the design document to the team by Friday",
        owner="Bob",
        deadline="2026-09-05",
        confidence=0.9,
        item_id="item-a",
    )
    item_b = _make_candidate(
        description="Design doc goes out end of week, Bob is handling it",
        source_quote="I'll send the design document to the team by Friday. I've already started drafting it.",
        owner=None,
        deadline="2026-09-05",  # valid deadline so it's not auto-rejected in step 1
        confidence=0.7,
        item_id="item-b",
    )

    # Mock deduplication LLM to identify them as duplicates
    dedup_response = [["item-a", "item-b"]]

    # Mock verification LLM to approve the merged item
    verify_response = {
        "status": "approved",
        "reason": "Well-grounded commitment by Bob.",
        "corrected_description": None,
        "corrected_owner": None,
        "corrected_deadline": None,
    }

    with patch("app.pipeline.verifier_agent.call_llm_json", new_callable=AsyncMock) as mock_llm:
        # First call = deduplication, second call = verification
        mock_llm.side_effect = [dedup_response, verify_response]
        results = await verify([item_a, item_b], SAMPLE_TRANSCRIPT)

    # Should result in exactly ONE approved item, not two
    approved = [r for r in results if r.status == VerificationStatus.APPROVED]
    assert len(approved) == 1

    # The merged item should have the best owner and deadline from both
    merged = approved[0]
    assert merged.final_task.owner == "Bob"  # from item_a
    assert merged.final_task.deadline == "2026-09-05"  # from item_a


@pytest.mark.asyncio
async def test_unique_items_not_merged():
    """Items that are clearly different should not be merged."""
    item_a = _make_candidate(
        description="Send the design document by Friday",
        source_quote="I'll send the design document to the team by Friday",
        owner="Bob",
        deadline="2026-09-05",
        item_id="item-a",
    )
    item_b = _make_candidate(
        description="Review the budget proposal by Wednesday",
        source_quote="I'll have the budget review done by next Wednesday",
        owner="Carol",
        deadline="2026-09-10",
        item_id="item-b",
    )

    # LLM identifies them as separate groups
    dedup_response = [["item-a"], ["item-b"]]

    verify_response_a = {
        "status": "approved",
        "reason": "Clear commitment by Bob.",
        "corrected_description": None,
        "corrected_owner": None,
        "corrected_deadline": None,
    }
    verify_response_b = {
        "status": "approved",
        "reason": "Clear commitment by Carol.",
        "corrected_description": None,
        "corrected_owner": None,
        "corrected_deadline": None,
    }

    with patch("app.pipeline.verifier_agent.call_llm_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [dedup_response, verify_response_a, verify_response_b]
        results = await verify([item_a, item_b], SAMPLE_TRANSCRIPT)

    approved = [r for r in results if r.status == VerificationStatus.APPROVED]
    assert len(approved) == 2


# ═══════════════════════════════════════════════
# Unit Tests for _merge_items helper
# ═══════════════════════════════════════════════


def test_merge_items_keeps_best_info():
    """Merged item should have the most specific owner, deadline, and highest confidence."""
    item_a = _make_candidate(
        description="Send the deck by Friday",
        source_quote="I'll send the deck by Friday",
        owner="Yashwant",
        deadline=None,
        confidence=0.8,
        item_id="a",
    )
    item_b = _make_candidate(
        description="The deck goes out end of week, Yashwant handles it",
        source_quote="deck goes out end of week, Yashwant",
        owner=None,
        deadline="2026-09-05",
        confidence=0.9,
        item_id="b",
    )

    merged = _merge_items([item_a, item_b])

    assert merged.owner == "Yashwant"  # from item_a
    assert merged.deadline == "2026-09-05"  # from item_b
    assert merged.confidence == 0.9  # max of both
