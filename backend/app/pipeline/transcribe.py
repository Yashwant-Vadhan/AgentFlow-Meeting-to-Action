"""
transcribe.py — TK-001: Whisper transcription (Yaashwanth SKP's module).

STUB IMPLEMENTATION — will be replaced by Yaashwanth's real module.
Provides the same function signature so the pipeline can call it now.

Real implementation will use faster-whisper with configurable model size.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def transcribe_chunk(audio_path: str) -> list[dict]:
    """
    Transcribe an audio chunk using faster-whisper.

    STUB: returns an empty list. Replace with real TK-001 implementation.

    Args:
        audio_path: Path to an audio file (.wav/.mp3/.m4a).

    Returns:
        List of dicts: {start: float, end: float, text: str, low_confidence: bool}
    """
    logger.warning("Using STUB transcriber — replace with real TK-001 implementation")
    logger.info("Would transcribe: %s", audio_path)
    return []
