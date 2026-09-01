"""
test_pipeline_integration.py — TV-003: Integration test harness.

Runs a short sample through the full pipeline:
  preprocess_audio -> chunk_audio -> transcribe_chunk -> extract -> verify

Uses REAL implementations for preprocess_audio and chunk_audio (Vishal's modules).
Uses CLEARLY-NAMED STUBS for stages that require external services (Whisper, LLM):
  - stub_transcribe_chunk() — returns hardcoded transcript segments
  - stub_extract()          — returns hardcoded candidate items
  - stub_verify()           — returns hardcoded verified items

Dependency injection: each pipeline stage is passed as a callable parameter,
so swapping in the real implementation later requires NO test rewrite — just
change the argument.
"""

import math
import os
import struct
import uuid
import wave
from datetime import date
from typing import Callable, Optional

import pytest

from app.models.schema import (
    CandidateItem,
    FinalTask,
    ItemType,
    VerificationStatus,
    VerifiedItem,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: Generate a synthetic test audio file
# ─────────────────────────────────────────────────────────────────────────────


def _generate_test_audio(path: str, duration_s: float = 10.0) -> str:
    """Generate a short synthetic WAV for integration testing."""
    import random

    sample_rate = 16000
    n_samples = int(sample_rate * duration_s)
    samples = []

    for i in range(n_samples):
        t = i / sample_rate
        value = 0.4 * math.sin(2 * math.pi * 440 * t)
        value += 0.05 * (random.random() * 2 - 1)
        value = max(-1.0, min(1.0, value))
        samples.append(int(value * 32767))

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))

    return path


@pytest.fixture
def test_audio(tmp_path):
    """A short synthetic WAV file for integration testing."""
    path = str(tmp_path / "integration_test.wav")
    return _generate_test_audio(path, duration_s=10.0)


# ─────────────────────────────────────────────────────────────────────────────
# Stubs for stages that require external services
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = (
    "Alright everyone, let's wrap up. Yashwant, can you send the project deck "
    "to the client by next Friday? And Sushil, please review the API documentation "
    "and update it before the end of the week. Also, we've decided to use PostgreSQL "
    "instead of MongoDB for the new service."
)


def stub_transcribe_chunk(audio_path: str) -> list[dict]:
    """
    STUB for transcribe_chunk (Yaashwanth SKP's module — TK-001).

    Returns a hardcoded transcript that contains clear action items
    for the extractor to find. Same function signature as the real module.
    """
    return [
        {"start": 0.0, "end": 5.0, "text": "Alright everyone, let's wrap up.", "low_confidence": False},
        {
            "start": 5.0,
            "end": 12.0,
            "text": "Yashwant, can you send the project deck to the client by next Friday?",
            "low_confidence": False,
        },
        {
            "start": 12.0,
            "end": 20.0,
            "text": "And Sushil, please review the API documentation and update it before the end of the week.",
            "low_confidence": False,
        },
        {
            "start": 20.0,
            "end": 28.0,
            "text": "Also, we've decided to use PostgreSQL instead of MongoDB for the new service.",
            "low_confidence": False,
        },
    ]


def stub_extract(transcript: str, meeting_date: Optional[str] = None) -> list[CandidateItem]:
    """
    STUB for extractor_agent.extract() (Yashwant's module — TY-001/TY-002).

    Returns hardcoded candidate items matching the shared schema.
    Same async-compatible signature as the real module (but sync for stub).
    """
    return [
        CandidateItem(
            id=f"item-{uuid.uuid4().hex[:8]}",
            type=ItemType.ACTION_ITEM,
            description="Send the project deck to the client by next Friday",
            owner="Yashwant",
            deadline=None,
            source_quote="Yashwant, can you send the project deck to the client by next Friday?",
            confidence=0.92,
        ),
        CandidateItem(
            id=f"item-{uuid.uuid4().hex[:8]}",
            type=ItemType.ACTION_ITEM,
            description="Review and update the API documentation before end of week",
            owner="Sushil",
            deadline=None,
            source_quote="Sushil, please review the API documentation and update it before the end of the week.",
            confidence=0.88,
        ),
        CandidateItem(
            id=f"item-{uuid.uuid4().hex[:8]}",
            type=ItemType.DECISION,
            description="Use PostgreSQL instead of MongoDB for the new service",
            owner=None,
            deadline=None,
            source_quote="we've decided to use PostgreSQL instead of MongoDB for the new service.",
            confidence=0.95,
        ),
    ]


def stub_verify(candidate_items: list[CandidateItem], transcript: str) -> list[VerifiedItem]:
    """
    STUB for verifier_agent.verify() (Sushil's module — TS-001/TS-002).

    Returns hardcoded verified items matching the shared schema.
    Same async-compatible signature as the real module (but sync for stub).
    """
    verified = []
    for item in candidate_items:
        if item.owner is None and item.deadline is None:
            verified.append(
                VerifiedItem(
                    id=item.id,
                    status=VerificationStatus.REJECTED,
                    reason="Both owner and deadline are missing — does not meet well-formed task bar.",
                    final_task=None,
                )
            )
        else:
            verified.append(
                VerifiedItem(
                    id=item.id,
                    status=VerificationStatus.APPROVED,
                    reason="Source quote verified in transcript; clear action with owner.",
                    final_task=FinalTask(
                        description=item.description,
                        owner=item.owner,
                        deadline=item.deadline,
                        type=item.type,
                    ),
                )
            )
    return verified


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline runner (dependency-injected)
# ─────────────────────────────────────────────────────────────────────────────


def run_pipeline(
    audio_path: str,
    preprocess_fn: Callable[[str], str],
    chunk_fn: Callable[[str, int], list[str]],
    transcribe_fn: Callable[[str], list[dict]],
    extract_fn: Callable,
    verify_fn: Callable,
    meeting_date: Optional[str] = None,
) -> list[VerifiedItem]:
    """
    Run the full pipeline with injectable stage functions.

    This allows swapping stubs for real implementations with zero rewrite.
    """
    # Stage 1: Preprocess audio
    cleaned_path = preprocess_fn(audio_path)
    assert os.path.exists(cleaned_path), f"Preprocessed file should exist: {cleaned_path}"

    # Stage 2: Chunk audio
    chunks = chunk_fn(cleaned_path, 45)
    assert isinstance(chunks, list), "chunk_fn should return a list"
    assert len(chunks) >= 1, "Should produce at least one chunk"

    # Stage 3: Transcribe each chunk
    all_segments = []
    for chunk_path in chunks:
        segments = transcribe_fn(chunk_path)
        assert isinstance(segments, list), "transcribe_fn should return a list"
        all_segments.extend(segments)

    # Combine transcript
    transcript = " ".join(seg["text"] for seg in all_segments if seg.get("text"))

    # Stage 4: Extract candidate items
    candidates = extract_fn(transcript, meeting_date)
    assert isinstance(candidates, list), "extract_fn should return a list"

    # Stage 5: Verify candidate items
    verified = verify_fn(candidates, transcript)
    assert isinstance(verified, list), "verify_fn should return a list"

    return verified


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPipelineIntegration:
    """
    Integration tests: run the full pipeline with real audio preprocessing
    and stub transcription/extraction/verification.
    """

    def test_full_pipeline_produces_verified_items(self, test_audio):
        """
        Full pipeline (preprocess -> chunk -> transcribe -> extract -> verify)
        produces a non-empty list of schema-valid verified items.
        """
        from app.pipeline.audio_preprocess import chunk_audio, preprocess_audio

        results = run_pipeline(
            audio_path=test_audio,
            preprocess_fn=preprocess_audio,
            chunk_fn=chunk_audio,
            transcribe_fn=stub_transcribe_chunk,
            extract_fn=stub_extract,
            verify_fn=stub_verify,
        )

        # Assert non-empty output
        assert len(results) > 0, "Pipeline should produce at least one verified item"

        # Assert all items are valid VerifiedItem objects
        for item in results:
            assert isinstance(item, VerifiedItem), f"Expected VerifiedItem, got {type(item)}"
            assert item.id, "Each item must have an id"
            assert item.status in [
                VerificationStatus.APPROVED,
                VerificationStatus.REJECTED,
                VerificationStatus.NEEDS_REVIEW,
            ], f"Invalid status: {item.status}"
            assert item.reason, "Each item must have a reason"

    def test_pipeline_has_approved_items(self, test_audio):
        """Pipeline should produce at least one approved item (from the sample transcript)."""
        from app.pipeline.audio_preprocess import chunk_audio, preprocess_audio

        results = run_pipeline(
            audio_path=test_audio,
            preprocess_fn=preprocess_audio,
            chunk_fn=chunk_audio,
            transcribe_fn=stub_transcribe_chunk,
            extract_fn=stub_extract,
            verify_fn=stub_verify,
        )

        approved = [r for r in results if r.status == VerificationStatus.APPROVED]
        assert len(approved) >= 1, "Should have at least one approved item"

        # Approved items should have a final_task
        for item in approved:
            assert item.final_task is not None, "Approved items must have a final_task"
            assert isinstance(item.final_task, FinalTask)
            assert item.final_task.description, "final_task.description must be non-empty"

    def test_pipeline_rejects_incomplete_items(self, test_audio):
        """Items with no owner AND no deadline should be rejected."""
        from app.pipeline.audio_preprocess import chunk_audio, preprocess_audio

        results = run_pipeline(
            audio_path=test_audio,
            preprocess_fn=preprocess_audio,
            chunk_fn=chunk_audio,
            transcribe_fn=stub_transcribe_chunk,
            extract_fn=stub_extract,
            verify_fn=stub_verify,
        )

        rejected = [r for r in results if r.status == VerificationStatus.REJECTED]
        # The decision item has no owner and no deadline — should be rejected
        assert len(rejected) >= 1, "Should reject items with neither owner nor deadline"

    def test_pipeline_with_empty_transcript(self, test_audio):
        """Pipeline handles an empty transcript gracefully — returns empty list."""
        from app.pipeline.audio_preprocess import chunk_audio, preprocess_audio

        def empty_transcribe(audio_path: str) -> list[dict]:
            return []

        def empty_extract(transcript: str, meeting_date=None) -> list[CandidateItem]:
            return []

        def empty_verify(candidates: list, transcript: str) -> list[VerifiedItem]:
            return []

        results = run_pipeline(
            audio_path=test_audio,
            preprocess_fn=preprocess_audio,
            chunk_fn=chunk_audio,
            transcribe_fn=empty_transcribe,
            extract_fn=empty_extract,
            verify_fn=empty_verify,
        )

        assert results == [], "Empty transcript should yield empty results"

    def test_stub_signatures_match_real_modules(self):
        """
        Verify that stub function signatures are compatible with real module signatures.

        This test ensures that when real implementations land, they can be
        swapped in without rewriting the test harness.
        """
        import inspect

        from app.pipeline.audio_preprocess import chunk_audio, preprocess_audio
        from app.pipeline.transcribe import transcribe_chunk

        # preprocess_audio(input_path: str) -> str
        sig = inspect.signature(preprocess_audio)
        assert "input_path" in sig.parameters

        # chunk_audio(audio_path: str, target_seconds: int) -> list[str]
        sig = inspect.signature(chunk_audio)
        assert "audio_path" in sig.parameters
        assert "target_seconds" in sig.parameters

        # transcribe_chunk(audio_path: str) -> list[dict]
        sig = inspect.signature(transcribe_chunk)
        assert "audio_path" in sig.parameters
