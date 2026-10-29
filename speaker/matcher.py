"""
Speaker matcher stub — match diarized segments against enrolled doctor.

Phase 4 will integrate with real speaker embeddings.
"""


def filter_doctor_segments(
    segments: list[dict], doctor_embedding=None
) -> list[dict]:
    """Keep only segments belonging to the enrolled doctor.

    Currently a stub — returns all segments unchanged.
    """
    return segments
