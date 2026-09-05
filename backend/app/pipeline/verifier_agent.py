"""
Verifier Agent — cross-checks candidate items against the transcript.

This module provides the second-pass verification for the extraction pipeline:
1. Deduplicates semantically similar candidate items (merging best info)
2. Verifies each item's source_quote against the transcript via LLM
3. Rejects hallucinations, hypotheticals, and incomplete items
4. Returns a list of VerifiedItems (approved / rejected / needs_review)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.llm_client import call_llm_json, call_llm
from app.models.schema import (
    CandidateItem,
    FinalTask,
    ItemType,
    VerificationStatus,
    VerifiedItem,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# System Prompts
# ═══════════════════════════════════════════════

VERIFICATION_SYSTEM_PROMPT = """You are a strict verification agent for a meeting-action-extraction system.
Your job is to verify whether a candidate action item or decision is genuinely grounded in the meeting transcript.

For each candidate item you receive, you must judge:

1. **Quote Verification**: Is the `source_quote` a real, verbatim or near-verbatim excerpt from the transcript?
   - The quote must actually appear (or very closely match) a passage in the transcript.
   - Minor whitespace or punctuation differences are acceptable.
   - Paraphrased or fabricated quotes are NOT acceptable.

2. **Semantic Verification**: Does the source_quote genuinely represent a decision or commitment?
   - A clear statement like "I'll send the report by Friday" = DECISION/COMMITMENT → approve
   - A question like "Should we send the report by Friday?" = QUESTION → reject
   - A hypothetical like "What if we sent the report by Friday?" = HYPOTHETICAL → reject
   - A suggestion that was explicitly rejected by the group = REJECTED SUGGESTION → reject
   - A vague statement with no clear owner or action = AMBIGUOUS → needs_review

3. **Completeness Check**: Is the extracted description accurate and complete?
   - Does it correctly capture the action/decision?
   - Is the owner correctly identified (if mentioned)?
   - Is the deadline correctly identified (if mentioned)?

Return your assessment as a JSON object with these fields:
{
  "status": "approved" | "rejected" | "needs_review",
  "reason": "One-sentence explanation of your judgment",
  "corrected_description": "Cleaned/improved description if approved, or null",
  "corrected_owner": "Corrected owner if different from original, or null",
  "corrected_deadline": "Corrected deadline if different from original, or null"
}

Be STRICT: when in doubt, mark as "needs_review" rather than approving.
Never invent information not present in the transcript.
Return ONLY the JSON object, no other text."""

DEDUPLICATION_SYSTEM_PROMPT = """You are a deduplication agent. Given a list of candidate action items extracted from a meeting transcript, identify which items describe the SAME underlying task or decision, just phrased differently.

Two items are duplicates if they refer to the same action, even if:
- They use different wording
- One mentions the owner and the other doesn't
- One has a deadline and the other doesn't
- They quote different parts of the transcript but describe the same task

Return a JSON array of groups. Each group is an array of item IDs that are duplicates of each other. Items that are unique (no duplicates) should appear as a single-element group.

Example: if items "a", "b" are duplicates and "c" is unique, return:
[["a", "b"], ["c"]]

Return ONLY the JSON array, no other text."""


# ═══════════════════════════════════════════════
# Main Verification Function
# ═══════════════════════════════════════════════


async def verify(
    candidate_items: list[CandidateItem],
    transcript: str,
) -> list[VerifiedItem]:
    """
    Verify a list of candidate items against the transcript.

    Pipeline:
    1. Auto-reject items missing both owner AND deadline
    2. Deduplicate semantically similar items (merge best info)
    3. For each remaining item, run LLM-based grounding verification
    4. Return a list of VerifiedItems

    Args:
        candidate_items: List of candidate items from the Extractor Agent.
        transcript: The full meeting transcript text.

    Returns:
        List of VerifiedItem objects with status, reason, and final_task.
    """
    if not candidate_items:
        logger.info("No candidate items to verify — returning empty list")
        return []

    logger.info(f"Verifying {len(candidate_items)} candidate items")

    verified_items: list[VerifiedItem] = []

    # ── Step 1: Auto-reject items missing both owner AND deadline ──
    valid_items: list[CandidateItem] = []
    for item in candidate_items:
        if item.owner is None and item.deadline is None:
            logger.info(
                f"Auto-rejecting item {item.id}: both owner and deadline are null"
            )
            verified_items.append(
                VerifiedItem(
                    id=item.id,
                    status=VerificationStatus.REJECTED,
                    reason="Rejected: both owner and deadline are missing — does not meet the well-formed task requirement.",
                    final_task=None,
                )
            )
        else:
            valid_items.append(item)

    if not valid_items:
        return verified_items

    # ── Step 2: Deduplicate ──
    deduplicated_items, duplicate_rejected = await _deduplicate_internal(valid_items)
    verified_items.extend(duplicate_rejected)
    logger.info(
        f"After deduplication: {len(valid_items)} → {len(deduplicated_items)} items ({len(duplicate_rejected)} duplicates marked rejected)"
    )

    # ── Step 3: LLM-based verification for each item ──
    for item in deduplicated_items:
        try:
            result = await _verify_single_item(item, transcript)
            verified_items.append(result)
        except Exception as e:
            # If LLM call fails, mark as needs_review rather than crashing
            logger.error(
                f"Verification failed for item {item.id}: {e}",
                exc_info=True,
            )
            verified_items.append(
                VerifiedItem(
                    id=item.id,
                    status=VerificationStatus.NEEDS_REVIEW,
                    reason=f"Verification failed due to an error: {str(e)[:200]}. Marked for manual review.",
                    final_task=FinalTask(
                        description=item.description,
                        owner=item.owner,
                        deadline=item.deadline,
                        type=item.type,
                    ),
                )
            )

    logger.info(
        f"Verification complete: "
        f"{sum(1 for v in verified_items if v.status == VerificationStatus.APPROVED)} approved, "
        f"{sum(1 for v in verified_items if v.status == VerificationStatus.REJECTED)} rejected, "
        f"{sum(1 for v in verified_items if v.status == VerificationStatus.NEEDS_REVIEW)} needs_review"
    )

    return verified_items


# ═══════════════════════════════════════════════
# Single-Item Verification (LLM Call)
# ═══════════════════════════════════════════════


async def _verify_single_item(
    item: CandidateItem,
    transcript: str,
) -> VerifiedItem:
    """Verify a single candidate item against the transcript using the LLM."""

    user_prompt = f"""Here is the full meeting transcript:
---
{transcript}
---

Here is the candidate item to verify:
- ID: {item.id}
- Type: {item.type.value}
- Description: {item.description}
- Owner: {item.owner or "Not specified"}
- Deadline: {item.deadline or "Not specified"}
- Source Quote: "{item.source_quote}"
- Confidence: {item.confidence}

Verify this item against the transcript and return your JSON assessment."""

    response = await call_llm_json(
        system_prompt=VERIFICATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Parse the LLM response
    if isinstance(response, list):
        # If the LLM returned an array, take the first element
        response = response[0] if response else {}

    status_str = response.get("status", "needs_review")
    reason = response.get("reason", "No reason provided by verifier.")

    # Map to enum
    try:
        status = VerificationStatus(status_str)
    except ValueError:
        logger.warning(f"Unknown verification status '{status_str}', defaulting to needs_review")
        status = VerificationStatus.NEEDS_REVIEW

    # Build final_task for approved / needs_review items
    final_task = None
    if status in (VerificationStatus.APPROVED, VerificationStatus.NEEDS_REVIEW):
        final_task = FinalTask(
            description=response.get("corrected_description") or item.description,
            owner=response.get("corrected_owner") or item.owner,
            deadline=response.get("corrected_deadline") or item.deadline,
            type=item.type,
        )

    return VerifiedItem(
        id=item.id,
        status=status,
        reason=reason,
        final_task=final_task,
    )


# ═══════════════════════════════════════════════
# Deduplication
# ═══════════════════════════════════════════════


async def deduplicate(
    items: list[CandidateItem],
) -> list[CandidateItem]:
    """Public deduplication helper (returns deduplicated items)."""
    deduped, _ = await _deduplicate_internal(items)
    return deduped


async def _deduplicate_internal(
    items: list[CandidateItem],
) -> tuple[list[CandidateItem], list[VerifiedItem]]:
    """
    Detect and merge duplicate candidate items.

    Uses the LLM to identify semantically similar items, then merges each
    group into a single item keeping the most specific owner and deadline.
    Any non-primary duplicates are recorded as rejected items so they don't
    remain stranded in the database.

    Args:
        items: List of candidate items to deduplicate.

    Returns:
        Tuple of (deduplicated_candidate_items, rejected_duplicate_verified_items).
    """
    if len(items) <= 1:
        return items, []

    # Build a summary for the LLM
    items_summary = []
    for item in items:
        items_summary.append({
            "id": item.id,
            "description": item.description,
            "owner": item.owner,
            "deadline": item.deadline,
        })

    user_prompt = f"""Here are the candidate action items to check for duplicates:

{json.dumps(items_summary, indent=2)}

Identify which items describe the same underlying task and group them.
Return ONLY a JSON array of groups (each group is an array of item IDs)."""

    try:
        groups = await call_llm_json(
            system_prompt=DEDUPLICATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except (ValueError, Exception) as e:
        logger.warning(f"Deduplication LLM call failed: {e}. Skipping deduplication.")
        return items, []

    if not isinstance(groups, list):
        logger.warning("Deduplication returned non-list response. Skipping.")
        return items, []

    # Build a lookup map
    item_map = {item.id: item for item in items}
    merged_items: list[CandidateItem] = []
    duplicate_rejected: list[VerifiedItem] = []
    seen_ids: set[str] = set()

    for group in groups:
        if not isinstance(group, list) or not group:
            continue

        # Collect all items in this group
        group_items = [item_map[gid] for gid in group if gid in item_map and gid not in seen_ids]
        if not group_items:
            continue

        for gid in group:
            seen_ids.add(gid)

        if len(group_items) == 1:
            # No duplicates in this group
            merged_items.append(group_items[0])
        else:
            # Merge duplicates — keep best info
            merged = _merge_items(group_items)
            logger.info(
                f"Merged {len(group_items)} duplicate items into one: "
                f"{[i.id for i in group_items]} → {merged.id}"
            )
            merged_items.append(merged)

            # Mark all other items in this duplicate group as rejected duplicates
            for other in group_items:
                if other.id != merged.id:
                    duplicate_rejected.append(
                        VerifiedItem(
                            id=other.id,
                            status=VerificationStatus.REJECTED,
                            reason=f"Duplicate task: merged into '{merged.description[:60]}'.",
                            final_task=None,
                        )
                    )

    # Add any items not covered by the LLM's groups (safety net)
    for item in items:
        if item.id not in seen_ids:
            merged_items.append(item)

    return merged_items, duplicate_rejected


def _merge_items(items: list[CandidateItem]) -> CandidateItem:
    """
    Merge multiple duplicate candidate items into one.

    Keeps:
    - The most specific owner (first non-null)
    - The most specific deadline (first non-null)
    - The longest/most descriptive description
    - The highest confidence score
    - The first item's source_quote
    - The first item's ID and type
    """
    # Sort by description length (longest first) to pick the best description
    sorted_items = sorted(items, key=lambda x: len(x.description), reverse=True)
    base = sorted_items[0]

    # Find the best owner (first non-null)
    best_owner = next((i.owner for i in items if i.owner), None)

    # Find the best deadline (first non-null)
    best_deadline = next((i.deadline for i in items if i.deadline), None)

    # Highest confidence
    best_confidence = max(i.confidence for i in items)

    return CandidateItem(
        id=base.id,
        type=base.type,
        description=base.description,
        owner=best_owner,
        deadline=best_deadline,
        source_quote=base.source_quote,
        confidence=best_confidence,
    )
