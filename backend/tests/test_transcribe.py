"""
test_transcribe.py — Unit tests for transcribe.py (TK-001).
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from app.pipeline.transcribe import transcribe_chunk, get_whisper_model


def test_transcribe_chunk_file_not_found():
    """Verify that a non-existent file path returns an empty list without raising an uncaught exception."""
    res = transcribe_chunk("/path/to/non_existent_audio.wav")
    assert res == []


@patch("app.pipeline.transcribe.get_whisper_model")
def test_transcribe_chunk_success(mock_get_model, tmp_path):
    """Test successful transcription parsing and confidence calculation."""
    dummy_audio = tmp_path / "test.wav"
    dummy_audio.write_bytes(b"dummy audio content")

    # Mock segment returned by faster-whisper
    mock_segment_1 = MagicMock()
    mock_segment_1.start = 0.0
    mock_segment_1.end = 2.5
    mock_segment_1.text = " Hello world"
    mock_segment_1.no_speech_prob = 0.05
    mock_segment_1.avg_logprob = -0.2

    mock_segment_2 = MagicMock()
    mock_segment_2.start = 2.5
    mock_segment_2.end = 5.0
    mock_segment_2.text = " Low confidence segment"
    mock_segment_2.no_speech_prob = 0.75
    mock_segment_2.avg_logprob = -1.5

    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment_1, mock_segment_2], mock_info)
    mock_get_model.return_value = mock_model

    results = transcribe_chunk(str(dummy_audio))

    assert len(results) == 2
    assert results[0] == {
        "start": 0.0,
        "end": 2.5,
        "text": "Hello world",
        "low_confidence": False,
    }
    assert results[1] == {
        "start": 2.5,
        "end": 5.0,
        "text": "Low confidence segment",
        "low_confidence": True,
    }
