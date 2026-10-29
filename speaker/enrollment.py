"""
Speaker enrollment stub.

Phase 3 will add real speaker embedding generation + storage.
"""


def enroll_doctor(doctor_id: str, audio_path: str) -> dict:
    """Generate and store a speaker embedding for a doctor.

    Currently a stub — returns a placeholder embedding.
    """
    return {
        "doctor_id": doctor_id,
        "embedding": None,
        "status": "stub — not yet implemented",
    }
