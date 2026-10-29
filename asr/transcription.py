"""
Transcription orchestrator — ties audio preprocessing → ASR → text normalization.
"""

from audio.preprocessing import preprocess
from asr.whisper_engine import transcribe as whisper_transcribe
from clinical.transcript_cleaner import clean as clean_transcript


def transcribe_audio(wav_path: str, model_size: str = "base") -> dict:
    """Full transcription pipeline: preprocess → ASR → transcript normalization.

    Steps:
      1. Audio preprocessing (DC removal, bandpass filter, RMS normalization)
      2. Whisper ASR with clinical vocabulary priming
      3. Transcript cleaning (spoken numbers, frequency abbreviations, split names)

    Returns the Whisper result dict with a cleaned 'text' field.
    """
    processed_path = preprocess(wav_path)
    result = whisper_transcribe(processed_path, model_size)

    # Normalize the raw transcript: spoken numbers, unit longforms,
    # frequency abbreviations, ASR split-word errors
    if result.get("text"):
        result["text"] = clean_transcript(result["text"])

    return result

