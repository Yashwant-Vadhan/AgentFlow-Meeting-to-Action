"""
transcribe.py — TK-001: Whisper transcription module (Yaashwanth SKP).

Uses `faster-whisper` to transcribe audio files into timestamped text segments with
confidence metrics.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global model cache to avoid re-loading weights for every audio chunk
_model_instance = None
_model_key = None


def get_whisper_model(model_size: Optional[str] = None, device: Optional[str] = None):
    """
    Lazy-load and cache the faster-whisper WhisperModel instance.
    """
    global _model_instance, _model_key

    settings = get_settings()
    size = model_size or settings.whisper_model_size
    dev = device or settings.whisper_device

    key = (size, dev)
    if _model_instance is not None and _model_key == key:
        return _model_instance

    try:
        from faster_whisper import WhisperModel

        logger.info(f"Loading faster-whisper model '{size}' on device '{dev}'...")
        compute_type = "int8" if dev == "cpu" else "float16"
        _model_instance = WhisperModel(size, device=dev, compute_type=compute_type)
        _model_key = key
        logger.info(f"faster-whisper model '{size}' loaded successfully.")
        return _model_instance
    except Exception as e:
        logger.error(f"Failed to load faster-whisper model ({size}, {dev}): {e}")
        raise e


def transcribe_chunk(audio_path: str, model_size: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Transcribe an audio chunk using faster-whisper.

    Args:
        audio_path: Path to an audio file (.wav/.mp3/.m4a).
        model_size: Optional override for model size (defaults to settings.whisper_model_size).

    Returns:
        List of dicts:
            [
                {
                    "start": float,
                    "end": float,
                    "text": str,
                    "low_confidence": bool
                },
                ...
            ]
    """
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return []

    try:
        model = get_whisper_model(model_size=model_size)
        segments_raw, info = model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        results: list[dict[str, Any]] = []

        for seg in segments_raw:
            text = seg.text.strip()
            if not text:
                continue

            # Flag low confidence if no_speech_prob is high (>0.6) or logprob is very negative (<-1.0)
            no_speech_prob = getattr(seg, "no_speech_prob", 0.0)
            avg_logprob = getattr(seg, "avg_logprob", 0.0)

            low_confidence = bool(no_speech_prob > 0.6 or avg_logprob < -1.0)

            results.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
                "low_confidence": low_confidence,
            })

        logger.info(
            f"Transcribed {audio_path}: {len(results)} segments extracted "
            f"(language={getattr(info, 'language', 'unknown')})"
        )
        return results

    except Exception as e:
        logger.error(f"Error transcribing audio file {audio_path}: {e}", exc_info=True)
        return []

