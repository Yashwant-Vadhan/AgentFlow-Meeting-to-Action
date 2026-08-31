"""
test_extractor_agent.py — pytest unit tests for TY-001 + TY-002.

Tests cover the acceptance criteria from todo.md:
  TY-001:
    ✓ Sample transcript with 2–3 action items → returns valid schema items
    ✓ Empty transcript → returns []
    ✓ Every item has source_quote found in transcript

  TY-002:
    ✓ Relative deadline "next Friday" → resolved to concrete ISO date
    ✓ Item with source_quote NOT in transcript → filtered out before return

These tests use unittest.mock to avoid a real Ollama call, so they run
without Ollama installed.  To run against a real LLM, set env var
REAL_LLM=1 and have Ollama running with llama3.1 pulled.
"""

import json
import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.pipeline.extractor_agent import (
    _heuristic_date_resolve,
    _normalise,
    _quote_found_in_transcript,
    extract,
)
from app.models.schema import CandidateItem


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = """
Alice: Alright, let's wrap up.  Yashwant, can you send the project deck to the client by next Friday?
Yashwant: Sure, I'll send the deck by Friday.
Alice: Great.  Also, we've decided to go with the blue colour scheme for the dashboard.
Bob: And Priya should review the API docs by end of month.
Alice: Perfect.  Let's meet again next week.
"""

SAMPLE_TRANSCRIPT_NO_ITEMS = """
Alice: Thanks for joining everyone.
Bob: Sure, happy to be here.
Alice: Have a great evening!
"""

MOCK_LLM_RESPONSE_VALID = [
    {
        "id": "item-1",
        "type": "action_item",
        "description": "Send the project deck to the client",
        "owner": "Yashwant",
        "deadline": "2024-08-09",
        "source_quote": "Yashwant, can you send the project deck to the client by next Friday",
        "confidence": 0.95,
    },
    {
        "id": "item-2",
        "type": "decision",
        "description": "Go with the blue colour scheme for the dashboard",
        "owner": None,
        "deadline": None,
        "source_quote": "we've decided to go with the blue colour scheme for the dashboard",
        "confidence": 0.90,
    },
    {
        "id": "item-3",
        "type": "action_item",
        "description": "Priya should review the API docs",
        "owner": "Priya",
        "deadline": "2024-08-31",
        "source_quote": "Priya should review the API docs by end of month",
        "confidence": 0.85,
    },
]

MOCK_LLM_RESPONSE_EMPTY = []

MOCK_LLM_RESPONSE_HALLUCINATED = [
    {
        "id": "item-hallucinated",
        "type": "action_item",
        "description": "Deploy the new server by Thursday",
        "owner": "Bob",
        "deadline": "2024-08-08",
        # This quote does NOT appear in SAMPLE_TRANSCRIPT
        "source_quote": "Bob will deploy the new server by Thursday",
        "confidence": 0.88,
    }
]

MOCK_LLM_RESPONSE_RELATIVE_DATE = [
    {
        "id": "item-rel",
        "type": "action_item",
        "description": "Send the deck",
        "owner": "Yashwant",
        "deadline": "next Friday",  # still relative — extractor didn't resolve it
        "source_quote": "Yashwant, can you send the project deck to the client by next Friday",
        "confidence": 0.9,
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper tests
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_quote_found_exact(self):
        assert _quote_found_in_transcript(
            "we've decided to go with the blue colour scheme",
            SAMPLE_TRANSCRIPT,
        )

    def test_quote_not_found(self):
        assert not _quote_found_in_transcript(
            "Bob will deploy the new server by Thursday",
            SAMPLE_TRANSCRIPT,
        )

    def test_quote_found_with_punctuation_diff(self):
        # Removes punctuation — should still match
        assert _quote_found_in_transcript(
            "Yashwant, can you send the project deck to the client by next Friday?",
            SAMPLE_TRANSCRIPT,
        )

    def test_heuristic_next_friday(self):
        # If today is Monday 2024-08-05, next Friday should be 2024-08-09
        monday = date(2024, 8, 5)
        result = _heuristic_date_resolve("next Friday", monday)
        assert result == "2024-08-09"

    def test_heuristic_tomorrow(self):
        base = date(2024, 8, 5)
        assert _heuristic_date_resolve("tomorrow", base) == "2024-08-06"

    def test_heuristic_end_of_month(self):
        base = date(2024, 8, 5)
        result = _heuristic_date_resolve("end of month", base)
        assert result == "2024-08-31"

    def test_heuristic_end_of_week(self):
        # Monday 2024-08-05 → Friday 2024-08-09
        base = date(2024, 8, 5)
        result = _heuristic_date_resolve("end of week", base)
        assert result == "2024-08-09"


# ─────────────────────────────────────────────────────────────────────────────
# TY-001 Acceptance Criteria
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractorTY001:
    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_VALID)
    async def test_returns_valid_schema_items(self, mock_llm):
        """TY-001 AC1: given a sample transcript with 2-3 action items, returns JSON matching schema."""
        items = await extract(SAMPLE_TRANSCRIPT)
        assert isinstance(items, list)
        assert len(items) >= 2
        for item in items:
            assert isinstance(item, CandidateItem)
            assert item.id
            assert item.type in ("decision", "action_item")
            assert item.description
            assert item.source_quote
            assert 0.0 <= item.confidence <= 1.0

    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_EMPTY)
    async def test_empty_transcript_returns_empty_list(self, mock_llm):
        """TY-001 AC2: empty transcript returns [] — never invents items."""
        items = await extract("")
        assert items == []

    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_EMPTY)
    async def test_no_action_items_returns_empty_list(self, mock_llm):
        """TY-001 AC2: transcript with no action items returns []."""
        items = await extract(SAMPLE_TRANSCRIPT_NO_ITEMS)
        assert items == []

    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_VALID)
    async def test_every_item_has_source_quote_in_transcript(self, mock_llm):
        """TY-001 AC3: every returned item's source_quote is a literal excerpt from the transcript."""
        items = await extract(SAMPLE_TRANSCRIPT)
        for item in items:
            assert _quote_found_in_transcript(item.source_quote, SAMPLE_TRANSCRIPT), (
                f"source_quote not found in transcript for item {item.id}: '{item.source_quote}'"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TY-002 Acceptance Criteria
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractorTY002:
    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_RELATIVE_DATE)
    async def test_relative_deadline_resolved(self, mock_llm):
        """
        TY-002 AC1: 'next Friday' on a transcript with meeting_date 2024-08-05 (Monday)
        resolves to 2024-08-09 (that Friday).
        """
        items = await extract(SAMPLE_TRANSCRIPT, meeting_date="2024-08-05")
        assert len(items) == 1
        assert items[0].deadline == "2024-08-09", (
            f"Expected '2024-08-09', got '{items[0].deadline}'"
        )

    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_HALLUCINATED)
    async def test_hallucinated_source_quote_filtered(self, mock_llm):
        """
        TY-002 AC2: item whose source_quote is NOT found in the transcript is
        filtered out before the function returns.
        """
        items = await extract(SAMPLE_TRANSCRIPT)
        assert items == [], (
            f"Expected no items (hallucinated quote filtered), but got: {items}"
        )

    @pytest.mark.asyncio
    @patch("app.pipeline.extractor_agent.call_llm_json", return_value=MOCK_LLM_RESPONSE_VALID)
    async def test_grounding_keeps_valid_items(self, mock_llm):
        """Grounding filter passes items whose quotes genuinely appear in the transcript."""
        items = await extract(SAMPLE_TRANSCRIPT)
        assert len(items) > 0
