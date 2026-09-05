"""
audio_preprocess.py — TV-001/TV-002: Audio & Video Preprocessing & Chunking.

TV-001 — preprocess_audio():
  • Extracts audio stream from video (.mp4, .mov, .mkv, .webm) or audio (.wav, .mp3, .m4a) via pydub
  • Normalizes volume (pydub.effects.normalize)
  • Applies noise reduction via noisereduce (spectral gating)
  • Applies a high-pass filter (~300 Hz) to cut low-frequency hum
  • Writes cleaned audio to a new 16kHz mono WAV file, returns its path

TV-002 — chunk_audio():
  • Splits cleaned audio into ~30–60 s chunks
  • Prefers silence boundaries (pydub.silence.detect_silence) near target length
  • Falls back to hard cut at target_seconds if no suitable silence gap
  • Returns list of chunk file paths
"""

import logging
import os
import struct
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.silence import detect_silence

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".mp4", ".mov", ".mkv", ".webm"}
HIGH_PASS_CUTOFF_HZ = 300
DEFAULT_EXPORT_FORMAT = "wav"

# Silence-detection defaults (for chunking)
SILENCE_THRESH_DB = -40          # dBFS below which audio is considered silence
MIN_SILENCE_LEN_MS = 400        # minimum silence length to be considered a gap
CHUNK_MIN_SECONDS = 30
CHUNK_MAX_SECONDS = 60


# ─────────────────────────────────────────────────────────────────────────────
# TV-001: Audio Preprocessing — noise handling
# ─────────────────────────────────────────────────────────────────────────────


def _apply_high_pass_filter(audio: AudioSegment, cutoff_hz: int = HIGH_PASS_CUTOFF_HZ) -> AudioSegment:
    """
    Apply a high-pass filter to remove low-frequency hum.
    """
    try:
        from pydub.effects import high_pass_filter
        return high_pass_filter(audio, cutoff_hz)
    except Exception as e:
        logger.warning("high_pass_filter failed (%s), returning original audio", e)
        return audio


def _apply_noise_reduction(audio: AudioSegment) -> AudioSegment:
    """
    Apply spectral-gating noise reduction using the noisereduce library.

    Uses the first 1 second of audio as a noise profile (or the full clip
    if shorter than 1 second).
    """
    try:
        import noisereduce as nr
    except ImportError:
        logger.warning(
            "noisereduce library not installed — skipping noise reduction. "
            "Install with: pip install noisereduce"
        )
        return audio

    samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
    sample_rate = audio.frame_rate

    # For multi-channel, process as mono then reconstruct
    # noisereduce works best on 1D arrays
    channels = audio.channels
    if channels > 1:
        samples = samples.reshape((-1, channels))
        reduced_channels = []
        for ch in range(channels):
            channel_data = samples[:, ch]
            reduced = nr.reduce_noise(
                y=channel_data,
                sr=sample_rate,
                prop_decrease=0.75,
                stationary=True,
            )
            reduced_channels.append(reduced)
        reduced_samples = np.column_stack(reduced_channels).flatten()
    else:
        reduced_samples = nr.reduce_noise(
            y=samples,
            sr=sample_rate,
            prop_decrease=0.75,
            stationary=True,
        )

    # Clip back to valid int16 range
    max_val = (2 ** (audio.sample_width * 8 - 1)) - 1
    min_val = -(2 ** (audio.sample_width * 8 - 1))
    reduced_samples = np.clip(reduced_samples, min_val, max_val).astype(np.int16)

    return audio._spawn(reduced_samples.tobytes())


def preprocess_audio(input_path: str) -> str:
    """
    Preprocess raw audio or video: normalize volume, apply noise reduction, high-pass filter.

    Args:
        input_path: Path to input audio/video file.

    Returns:
        Path to the cleaned audio file (WAV format).

    Raises:
        FileNotFoundError: If input_path does not exist.
        ValueError: If file format is unsupported.
        RuntimeError: If audio processing fails (e.g., corrupted file).
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    ext = input_file.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported audio format '{ext}'. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )

    logger.info("Preprocessing audio: %s", input_path)

    try:
        # Load audio stream from audio or video file via pydub
        audio = AudioSegment.from_file(input_path)

        logger.info(
            "Loaded audio: duration=%.1fs, channels=%d, sample_rate=%d, sample_width=%d",
            len(audio) / 1000.0,
            audio.channels,
            audio.frame_rate,
            audio.sample_width,
        )

    except Exception as exc:
        raise RuntimeError(f"Failed to load audio file '{input_path}': {exc}") from exc

    # Step 1: Normalize volume
    audio = normalize(audio)
    logger.info("Volume normalized")

    # Step 2: Apply noise reduction (spectral gating)
    try:
        audio = _apply_noise_reduction(audio)
        logger.info("Noise reduction applied")
    except Exception as exc:
        logger.warning("Noise reduction failed (continuing without it): %s", exc)

    # Step 3: Apply high-pass filter to cut low-frequency hum
    try:
        audio = _apply_high_pass_filter(audio, HIGH_PASS_CUTOFF_HZ)
        logger.info("High-pass filter applied (cutoff=%d Hz)", HIGH_PASS_CUTOFF_HZ)
    except Exception as exc:
        logger.warning("High-pass filter failed (continuing without it): %s", exc)

    # Convert to 16kHz mono audio (optimal for Whisper STT)
    audio = audio.set_frame_rate(16000).set_channels(1)

    # Write cleaned audio to a new file
    output_path = str(input_file.parent / f"{input_file.stem}_cleaned.wav")
    audio.export(output_path, format=DEFAULT_EXPORT_FORMAT)

    output_size = os.path.getsize(output_path)
    logger.info("Cleaned audio written: %s (%.1f KB)", output_path, output_size / 1024.0)

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# TV-002: Audio Chunking
# ─────────────────────────────────────────────────────────────────────────────


def chunk_audio(audio_path: str, target_seconds: int = 45) -> list[str]:
    """
    Split audio into ~30–60 second chunks, preferring silence boundaries.

    Uses pydub's silence detection to find natural break points near the
    target chunk length. If no suitable silence gap exists near the target,
    falls back to a hard cut at target_seconds.

    Args:
        audio_path: Path to a preprocessed audio file.
        target_seconds: Target chunk duration in seconds (default 45).

    Returns:
        List of file paths to the chunk files.

    Raises:
        FileNotFoundError: If audio_path does not exist.
        RuntimeError: If audio cannot be loaded or chunked.
    """
    audio_file = Path(audio_path)

    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Chunking audio: %s (target=%ds)", audio_path, target_seconds)

    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load audio for chunking: {exc}") from exc

    duration_ms = len(audio)
    duration_s = duration_ms / 1000.0

    # If the audio is already short enough, return it as a single chunk
    if duration_s <= CHUNK_MAX_SECONDS:
        logger.info("Audio is %.1fs — short enough, returning as single chunk", duration_s)
        return [audio_path]

    # Detect silence boundaries
    try:
        silences = detect_silence(
            audio,
            min_silence_len=MIN_SILENCE_LEN_MS,
            silence_thresh=audio.dBFS + SILENCE_THRESH_DB if audio.dBFS > -float("inf") else SILENCE_THRESH_DB,
        )
        # Convert silence ranges to midpoints (good split candidates)
        silence_midpoints_ms = [(start + end) // 2 for start, end in silences]
        logger.info("Detected %d silence gaps", len(silence_midpoints_ms))
    except Exception as exc:
        logger.warning("Silence detection failed: %s — using fixed-length chunking", exc)
        silence_midpoints_ms = []

    target_ms = target_seconds * 1000
    min_ms = CHUNK_MIN_SECONDS * 1000
    max_ms = CHUNK_MAX_SECONDS * 1000

    chunks: list[AudioSegment] = []
    current_pos = 0

    while current_pos < duration_ms:
        remaining = duration_ms - current_pos

        # If remaining audio fits in one chunk, take it all
        if remaining <= max_ms:
            chunks.append(audio[current_pos:])
            break

        # Find the best silence midpoint near the target length
        ideal_split = current_pos + target_ms
        best_split = None
        best_distance = float("inf")

        for midpoint in silence_midpoints_ms:
            if midpoint <= current_pos + min_ms:
                continue  # too early — chunk would be too short
            if midpoint > current_pos + max_ms:
                continue  # too late — chunk would be too long

            distance = abs(midpoint - ideal_split)
            if distance < best_distance:
                best_distance = distance
                best_split = midpoint

        if best_split is not None:
            # Split at the best silence gap
            chunks.append(audio[current_pos:best_split])
            current_pos = best_split
            logger.debug("Split at silence gap: %d ms", best_split)
        else:
            # No suitable silence gap — hard cut at target
            split_point = current_pos + target_ms
            if split_point >= duration_ms:
                chunks.append(audio[current_pos:])
                break
            chunks.append(audio[current_pos:split_point])
            current_pos = split_point
            logger.debug("Hard cut at: %d ms (no silence gap found)", split_point)

    # Write chunks to disk
    chunk_dir = audio_file.parent
    chunk_paths: list[str] = []

    for idx, chunk in enumerate(chunks):
        chunk_filename = f"{audio_file.stem}_chunk_{idx + 1:03d}.wav"
        chunk_path = str(chunk_dir / chunk_filename)
        chunk.export(chunk_path, format=DEFAULT_EXPORT_FORMAT)
        chunk_duration_s = len(chunk) / 1000.0
        chunk_paths.append(chunk_path)
        logger.info(
            "Chunk %d/%d: %.1fs → %s",
            idx + 1,
            len(chunks),
            chunk_duration_s,
            chunk_path,
        )

    logger.info(
        "Chunking complete: %d chunks from %.1fs audio",
        len(chunk_paths),
        duration_s,
    )

    return chunk_paths
