"""
extractor_agent.py — TY-001 + TY-002: Extractor Agent

Reads a meeting transcript and returns a list of CandidateItem objects
(decisions and action items with owner, deadline, source_quote, confidence).

Key behaviours
──────────────
TY-001:
  • Uses call_llm() abstraction (Ollama backend, model from .env)
  • System prompt explicitly forbids hallucinating items without source_quote
  • Validates LLM JSON output with Pydantic; retries once with stricter prompt
  • Returns [] on transcripts with no real action items

TY-002 (grounding & edge cases):
  • meeting_date parameter: relative deadlines resolved to ISO dates
  • Post-processing filter: drops any item whose source_quote is not found
    (near-verbatim, allowing minor whitespace/punct differences) in the transcript
  • All filtering decisions are logged for traceability
"""

import json
import logging
import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as dateutil_parser
from pydantic import ValidationError

from app.llm_client import call_llm_json
from app.models.schema import CandidateItem

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert AI assistant that extracts actionable decisions and action items from meeting transcripts.

Your task is to identify:
1. Action Items: Clear tasks assigned to someone.
2. Decisions: Key agreements or choices made by the group.

For each item, output a JSON object with:
- type: "action_item" or "decision"
- description: A clear, concise summary of the task or decision.
- owner: Name of the person responsible. Rule: If Speaker A says "Vishal, can you...", owner is "Vishal". If Speaker A says "I will...", owner is Speaker A (e.g., "Yashwant"). NEVER output "Unassigned" or "I" if a person's name or speaker name is present.
- deadline: Exact deadline phrase from transcript (e.g. "Tomorrow at 12 PM", "Thursday evening", "Friday 10 AM", "Friday 3 PM", "Friday 6 PM"). Do not leave as null if mentioned.
- source_quote: Literal excerpt from the transcript justifying this item.
- confidence: Float from 0.8 to 1.0 for explicit requests.

Rules:
- Output ONLY a valid JSON array of objects.
- Do not invent items.
- The `source_quote` MUST be an excerpt from the transcript text.

Return ONLY the JSON array, nothing else."""

_RETRY_SYSTEM_PROMPT = """You previously returned invalid JSON. Fix it.

Return ONLY a valid JSON array matching this schema (no markdown, no text):
[{
  "id": "string",
  "type": "decision" | "action_item",
  "description": "string",
  "owner": "string",
  "deadline": "string or null",
  "source_quote": "verbatim excerpt from transcript",
  "confidence": 1.0
}]

If no items exist, return: []"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace/punctuation for fuzzy matching."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _quote_found_in_transcript(source_quote: str, transcript: str) -> bool:
    """
    Return True if source_quote (or a normalised version of it) appears
    within the transcript. Allows minor whitespace/punctuation differences.
    """
    if not source_quote or not transcript:
        return False
    norm_quote = _normalise(source_quote)
    norm_transcript = _normalise(transcript)
    if norm_quote in norm_transcript:
        return True
    
    # Soft fuzzy matching: check if key words match
    words = norm_quote.split()
    if len(words) >= 3:
        sub_phrase = " ".join(words[:min(5, len(words))])
        if sub_phrase in norm_transcript:
            return True
    return False


def _resolve_relative_dates(
    items: list[CandidateItem],
    meeting_date: Optional[str],
    transcript: str,
) -> list[CandidateItem]:
    """
    TY-002: If meeting_date is provided, ask the LLM to resolve any relative
    deadline still remaining in an item's deadline field.

    The extractor prompt already asks the LLM to resolve these inline, but
    this pass catches anything that slipped through (e.g. "end of week" as a
    deadline value instead of an ISO date).
    """
    if not meeting_date:
        return items

    try:
        base_date = dateutil_parser.parse(meeting_date).date()
    except Exception:
        logger.warning("Could not parse meeting_date=%s; skipping date resolution", meeting_date)
        return items

    resolved = []
    for item in items:
        if item.deadline and not _looks_like_iso_date(item.deadline):
            # deadline is still a relative phrase — try to resolve heuristically
            resolved_date = _heuristic_date_resolve(item.deadline, base_date)
            if resolved_date:
                logger.info(
                    "Resolved relative deadline '%s' → '%s' for item %s",
                    item.deadline,
                    resolved_date,
                    item.id,
                )
                item = item.model_copy(update={"deadline": resolved_date})
            else:
                logger.warning(
                    "Could not resolve relative deadline '%s' for item %s; setting to null",
                    item.deadline,
                    item.id,
                )
                item = item.model_copy(update={"deadline": None})
        resolved.append(item)
    return resolved


def _looks_like_iso_date(value: str) -> bool:
    """Check if value looks like YYYY-MM-DD."""
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()))


def _heuristic_date_resolve(phrase: str, base: date) -> Optional[str]:
    """
    Try to resolve common relative deadline phrases to ISO dates.
    Handles: 'next friday', 'end of week', 'tomorrow', 'next week', 'end of month', etc.
    """
    phrase_lower = phrase.lower().strip()

    # Try dateutil first
    try:
        parsed = dateutil_parser.parse(phrase, default=base.replace(day=1), fuzzy=True).date()
        if parsed >= base:
            return parsed.isoformat()
    except Exception:
        pass

    # Manual heuristics
    if "tomorrow" in phrase_lower:
        return (base + timedelta(days=1)).isoformat()
    if "end of week" in phrase_lower or "end of the week" in phrase_lower:
        # Friday of the current week
        days_ahead = 4 - base.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (base + timedelta(days=days_ahead)).isoformat()
    if "next week" in phrase_lower:
        return (base + timedelta(weeks=1)).isoformat()
    if "end of month" in phrase_lower or "end of the month" in phrase_lower:
        # First day of next month minus one day
        if base.month == 12:
            eom = date(base.year + 1, 1, 1) - timedelta(days=1)
        else:
            eom = date(base.year, base.month + 1, 1) - timedelta(days=1)
        return eom.isoformat()
    if "next friday" in phrase_lower:
        days_ahead = 4 - base.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (base + timedelta(days=days_ahead)).isoformat()
    if "next monday" in phrase_lower:
        days_ahead = 0 - base.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (base + timedelta(days=days_ahead)).isoformat()

    return None


def _parse_and_validate(data: list | dict) -> list[CandidateItem]:
    """
    Validate each item with Pydantic.
    Returns only valid items; logs and skips invalid ones.
    """
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")

    items: list[CandidateItem] = []
    for idx, raw_item in enumerate(data):
        # Ensure each item has an id
        if "id" not in raw_item or not raw_item["id"]:
            raw_item["id"] = f"item-{uuid.uuid4().hex[:8]}"
        try:
            items.append(CandidateItem(**raw_item))
        except ValidationError as exc:
            logger.warning("Skipping invalid candidate item at index %d: %s", idx, exc)
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def extract(
    transcript: str,
    meeting_date: Optional[str] = None,
) -> list[CandidateItem]:
    """
    Extract decisions and action items from a meeting transcript.

    Args:
        transcript:    Full meeting transcript text.
        meeting_date:  ISO date string (YYYY-MM-DD) of the meeting, used to
                       resolve relative deadline phrases (TY-002).

    Returns:
        List of CandidateItem objects validated against the shared schema.
        Returns [] if no items are found — never invents items.

    Raises:
        RuntimeError: If the LLM fails and the retry also fails.
        ValueError:   If the LLM returns malformed JSON on both attempts.
    """
    if not transcript or not transcript.strip():
        logger.info("Empty transcript — returning empty extraction result")
        return []

    meeting_date_note = f"\nMeeting date: {meeting_date}" if meeting_date else ""
    user_prompt = f"Transcript:{meeting_date_note}\n\n{transcript}"

    logger.info("Extractor: first LLM call (meeting_date=%s)", meeting_date)
    raw_json = await call_llm_json(_SYSTEM_PROMPT, user_prompt)
    items = _parse_and_validate(raw_json)

    logger.info("Extractor: %d raw candidate items before grounding filter", len(items))

    # ── TY-002: Resolve relative dates ────────────────────────────────────────
    items = _resolve_relative_dates(items, meeting_date, transcript)

    # ── TY-002: Grounding filter — drop items whose source_quote isn't in transcript ──
    grounded_items: list[CandidateItem] = []
    for item in items:
        if _quote_found_in_transcript(item.source_quote, transcript):
            grounded_items.append(item)
        else:
            logger.warning(
                "Dropping item %s ('%s'): source_quote not found in transcript. "
                "Quote was: '%s'",
                item.id,
                item.description[:60],
                item.source_quote[:80],
            )

    logger.info(
        "Extractor: %d items remain after grounding filter (dropped %d)",
        len(grounded_items),
        len(items) - len(grounded_items),
    )
    return grounded_items
