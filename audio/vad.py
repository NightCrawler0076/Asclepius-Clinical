"""
Voice Activity Detection stub.

Phase 2 will integrate silero-vad or webrtcvad.
"""


def detect_speech_segments(wav_path: str) -> list[dict]:
    """Return speech segments from an audio file.

    Currently returns a single segment covering the entire file.
    Future: use silero-vad for real segmentation.

    Returns list of {start: float, end: float} dicts (seconds).
    """
    import scipy.io.wavfile as wavfile

    sr, data = wavfile.read(wav_path)
    duration = len(data) / sr
    return [{"start": 0.0, "end": duration}]
