"""
audio_preprocess.py — Audio & Video Preprocessing Module.

Extracts audio from video formats (.mp4, .mov, .mkv, .webm) and audio formats (.mp3, .wav, .m4a),
normalizes volume, and exports clean 16kHz mono WAV chunks for Whisper transcription.
"""

import logging
import os

logger = logging.getLogger(__name__)


def preprocess_audio(input_path: str) -> str:
    """
    Preprocess audio or video file:
    - Extracts audio stream from video files (.mp4, .mov, .mkv, .webm) or loads audio (.mp3, .wav, .m4a).
    - Normalizes volume and converts to 16kHz mono WAV (optimal for Whisper).

    Args:
        input_path: Path to input audio or video file.

    Returns:
        Path to the cleaned WAV audio file.
    """
    if not os.path.exists(input_path):
        logger.error(f"Input media file not found: {input_path}")
        return input_path

    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_cleaned.wav"

    try:
        from pydub import AudioSegment

        logger.info(f"Preprocessing media file: {input_path}")
        audio = AudioSegment.from_file(input_path)

        # Normalize volume level
        audio = audio.normalize()

        # Convert to 16kHz mono audio — ideal for Whisper STT
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(output_path, format="wav")

        logger.info(f"Successfully extracted and normalized audio to: {output_path}")
        return output_path

    except Exception as e:
        logger.warning(f"pydub audio extraction failed for {input_path}: {e}. Passing raw file to Whisper.")
        return input_path


def chunk_audio(audio_path: str, target_seconds: int = 45) -> list[str]:
    """
    Split audio into 30-60 second chunks for processing.

    Args:
        audio_path: Path to a preprocessed audio file.
        target_seconds: Target chunk duration.

    Returns:
        List of file paths to the chunk files.
    """
    if not os.path.exists(audio_path):
        return [audio_path]

    try:
        from pydub import AudioSegment
        from pydub.silence import split_on_silence

        audio = AudioSegment.from_file(audio_path)
        duration_sec = len(audio) / 1000.0

        # If audio is under 60 seconds, no chunking needed
        if duration_sec <= 60:
            return [audio_path]

        # Chunk audio every ~45 seconds
        target_ms = target_seconds * 1000
        chunks = []
        base, _ = os.path.splitext(audio_path)

        for i, start_ms in enumerate(range(0, len(audio), target_ms)):
            end_ms = min(start_ms + target_ms, len(audio))
            chunk_segment = audio[start_ms:end_ms]
            chunk_file = f"{base}_chunk_{i}.wav"
            chunk_segment.export(chunk_file, format="wav")
            chunks.append(chunk_file)

        logger.info(f"Chunked {audio_path} into {len(chunks)} segments (~{target_seconds}s each)")
        return chunks

    except Exception as e:
        logger.warning(f"Audio chunking failed: {e}. Returning full file as single chunk.")
        return [audio_path]

