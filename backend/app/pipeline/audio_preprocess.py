"""
audio_preprocess.py — TV-001/TV-002: Audio preprocessing (Vishal's module).

STUB IMPLEMENTATION — will be replaced by Vishal's real module.
Provides the same function signatures so the pipeline can call them now.

Real implementation will use pydub + ffmpeg for noise reduction and chunking.
"""

import logging

logger = logging.getLogger(__name__)


def preprocess_audio(input_path: str) -> str:
    """
    Preprocess raw audio: normalize volume, apply noise reduction.

    STUB: returns the input path unchanged. Replace with real TV-001 implementation.

    Args:
        input_path: Path to raw audio file (.wav/.mp3/.m4a).

    Returns:
        Path to the cleaned audio file.
    """
    logger.warning("Using STUB audio preprocessor — replace with real TV-001 implementation")
    return input_path


def chunk_audio(audio_path: str, target_seconds: int = 45) -> list[str]:
    """
    Split audio into 30-60 second chunks, preferring silence boundaries.

    STUB: returns the input path as a single chunk.
    Replace with real TV-002 implementation.

    Args:
        audio_path: Path to a preprocessed audio file.
        target_seconds: Target chunk duration.

    Returns:
        List of file paths to the chunk files.
    """
    logger.warning("Using STUB audio chunker — replace with real TV-002 implementation")
    return [audio_path]
