"""
Speaker diarization stub.

Phase 4 will add real diarization (e.g. pyannote.audio).
"""


def diarize(audio_path: str) -> list[dict]:
    """Segment audio by speaker.

    Currently a stub — assigns all audio to speaker_0.
    Returns list of {speaker: str, start: float, end: float}.
    """
    import scipy.io.wavfile as wavfile

    sr, data = wavfile.read(audio_path)
    duration = len(data) / sr
    return [{"speaker": "speaker_0", "start": 0.0, "end": duration}]
