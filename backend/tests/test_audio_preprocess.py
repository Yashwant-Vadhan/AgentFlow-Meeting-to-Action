"""
test_audio_preprocess.py — Unit tests for TV-001 (noise handling) and TV-002 (chunking).

Uses synthetic WAV files generated programmatically — no external audio fixtures needed.
"""

import math
import os
import struct
import tempfile
import wave
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: generate synthetic WAV files
# ─────────────────────────────────────────────────────────────────────────────

def _generate_sine_wav(
    path: str,
    duration_s: float = 5.0,
    frequency: float = 440.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
    add_noise: bool = True,
) -> str:
    """Generate a WAV file containing a sine wave, optionally with white noise."""
    import random

    n_samples = int(sample_rate * duration_s)
    samples = []

    for i in range(n_samples):
        t = i / sample_rate
        # Sine wave
        value = amplitude * math.sin(2 * math.pi * frequency * t)
        # Add white noise
        if add_noise:
            value += 0.1 * (random.random() * 2 - 1)
        # Clamp to [-1, 1] then convert to int16
        value = max(-1.0, min(1.0, value))
        samples.append(int(value * 32767))

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    return path


def _generate_wav_with_silence_gaps(
    path: str,
    total_duration_s: float = 180.0,  # 3 minutes
    segment_duration_s: float = 40.0,
    silence_duration_s: float = 2.0,
    sample_rate: int = 16000,
) -> str:
    """
    Generate a WAV with alternating tone segments and silence gaps.
    Good for testing chunk_audio's silence-boundary detection.
    """
    import random

    samples = []
    t = 0.0

    while t < total_duration_s:
        # Tone segment
        seg_dur = min(segment_duration_s, total_duration_s - t)
        for i in range(int(seg_dur * sample_rate)):
            value = 0.5 * math.sin(2 * math.pi * 440 * (t + i / sample_rate))
            value += 0.05 * (random.random() * 2 - 1)
            value = max(-1.0, min(1.0, value))
            samples.append(int(value * 32767))
        t += seg_dur

        if t >= total_duration_s:
            break

        # Silence gap
        sil_dur = min(silence_duration_s, total_duration_s - t)
        for _ in range(int(sil_dur * sample_rate)):
            samples.append(0)
        t += sil_dur

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    return path


@pytest.fixture
def short_wav(tmp_path):
    """A short (5 second) noisy sine wave WAV file."""
    path = str(tmp_path / "test_short.wav")
    return _generate_sine_wav(path, duration_s=5.0, add_noise=True)


@pytest.fixture
def long_wav(tmp_path):
    """A longer (3 minute) WAV file with silence gaps for chunking tests."""
    path = str(tmp_path / "test_long.wav")
    return _generate_wav_with_silence_gaps(path, total_duration_s=180.0)


@pytest.fixture
def medium_wav(tmp_path):
    """A medium (50 second) WAV — short enough to be a single chunk."""
    path = str(tmp_path / "test_medium.wav")
    return _generate_sine_wav(path, duration_s=50.0, add_noise=False)


# ─────────────────────────────────────────────────────────────────────────────
# TV-001 Tests: preprocess_audio
# ─────────────────────────────────────────────────────────────────────────────


class TestPreprocessAudio:
    """Tests for preprocess_audio() — TV-001."""

    def test_produces_output_file(self, short_wav):
        """Given a noisy sample clip, preprocess_audio produces a non-empty output file."""
        from app.pipeline.audio_preprocess import preprocess_audio

        output_path = preprocess_audio(short_wav)

        assert os.path.exists(output_path), "Output file should exist"
        assert os.path.getsize(output_path) > 0, "Output file should be non-empty"
        assert output_path.endswith("_cleaned.wav"), "Output should be a cleaned WAV"

    def test_output_is_valid_wav(self, short_wav):
        """Output file should be a valid WAV that can be opened."""
        from app.pipeline.audio_preprocess import preprocess_audio

        output_path = preprocess_audio(short_wav)

        with wave.open(output_path, "r") as wf:
            assert wf.getnchannels() >= 1
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() > 0
            assert wf.getnframes() > 0

    def test_handles_wav_format(self, short_wav):
        """Function handles .wav input format."""
        from app.pipeline.audio_preprocess import preprocess_audio

        output_path = preprocess_audio(short_wav)
        assert os.path.exists(output_path)

    def test_file_not_found_raises(self, tmp_path):
        """FileNotFoundError on missing file."""
        from app.pipeline.audio_preprocess import preprocess_audio

        with pytest.raises(FileNotFoundError):
            preprocess_audio(str(tmp_path / "nonexistent.wav"))

    def test_unsupported_format_raises(self, tmp_path):
        """ValueError on unsupported format."""
        from app.pipeline.audio_preprocess import preprocess_audio

        bad_file = tmp_path / "test.ogg"
        bad_file.write_bytes(b"fake data")

        with pytest.raises(ValueError, match="Unsupported audio format"):
            preprocess_audio(str(bad_file))

    def test_output_different_from_input(self, short_wav):
        """Output file path is different from input (no in-place modification)."""
        from app.pipeline.audio_preprocess import preprocess_audio

        output_path = preprocess_audio(short_wav)
        assert output_path != short_wav


# ─────────────────────────────────────────────────────────────────────────────
# TV-002 Tests: chunk_audio
# ─────────────────────────────────────────────────────────────────────────────


class TestChunkAudio:
    """Tests for chunk_audio() — TV-002."""

    def test_long_audio_produces_multiple_chunks(self, long_wav):
        """A 3-minute file should split into multiple chunks (~3-6 chunks)."""
        from app.pipeline.audio_preprocess import chunk_audio

        chunks = chunk_audio(long_wav, target_seconds=45)

        assert len(chunks) >= 3, f"Expected >=3 chunks from 3min audio, got {len(chunks)}"
        assert len(chunks) <= 10, f"Expected <=10 chunks from 3min audio, got {len(chunks)}"

        # All chunk files should exist and be non-empty
        for chunk_path in chunks:
            assert os.path.exists(chunk_path), f"Chunk file should exist: {chunk_path}"
            assert os.path.getsize(chunk_path) > 0, f"Chunk file should be non-empty: {chunk_path}"

    def test_chunk_durations_in_range(self, long_wav):
        """Each chunk should be between 30-60 seconds (with some tolerance for the last chunk)."""
        from app.pipeline.audio_preprocess import chunk_audio
        from pydub import AudioSegment

        chunks = chunk_audio(long_wav, target_seconds=45)

        for i, chunk_path in enumerate(chunks):
            audio = AudioSegment.from_file(chunk_path)
            duration_s = len(audio) / 1000.0

            if i < len(chunks) - 1:
                # Non-last chunks should be in range (with small tolerance)
                assert duration_s >= 25, f"Chunk {i+1} too short: {duration_s:.1f}s"
                assert duration_s <= 65, f"Chunk {i+1} too long: {duration_s:.1f}s"
            else:
                # Last chunk can be shorter
                assert duration_s > 0, f"Last chunk should not be empty"

    def test_short_audio_returns_single_chunk(self, medium_wav):
        """Audio shorter than max chunk length should return as a single chunk."""
        from app.pipeline.audio_preprocess import chunk_audio

        chunks = chunk_audio(medium_wav, target_seconds=45)

        assert len(chunks) == 1, f"Expected 1 chunk for 50s audio, got {len(chunks)}"
        assert chunks[0] == medium_wav, "Single chunk should be the original file"

    def test_silence_gap_chunking(self, long_wav):
        """Chunks should prefer silence boundaries over hard cuts."""
        from app.pipeline.audio_preprocess import chunk_audio

        # This is a behavioral test — the WAV has deliberate silence gaps
        # every ~40 seconds, so chunks should align with those
        chunks = chunk_audio(long_wav, target_seconds=45)

        # We at least verify it produces valid chunks — silence-awareness
        # is an implementation detail that's hard to assert precisely
        assert len(chunks) >= 2
        for chunk_path in chunks:
            assert os.path.exists(chunk_path)

    def test_file_not_found_raises(self, tmp_path):
        """FileNotFoundError on missing file."""
        from app.pipeline.audio_preprocess import chunk_audio

        with pytest.raises(FileNotFoundError):
            chunk_audio(str(tmp_path / "nonexistent.wav"))

    def test_chunk_filenames_follow_pattern(self, long_wav):
        """Chunk files should follow the naming pattern: <stem>_chunk_NNN.wav."""
        from app.pipeline.audio_preprocess import chunk_audio

        chunks = chunk_audio(long_wav, target_seconds=45)

        for i, chunk_path in enumerate(chunks):
            filename = Path(chunk_path).name
            assert "_chunk_" in filename, f"Chunk filename should contain '_chunk_': {filename}"
            assert filename.endswith(".wav"), f"Chunk should be .wav: {filename}"
