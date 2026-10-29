"""
Prescription schema — the canonical prescription object.
"""

import uuid
from datetime import datetime, timezone


def new_prescription(
    doctor_id: str = "",
    patient: dict | None = None,
    complaints: list | None = None,
    diagnosis: list | None = None,
    medications: list | None = None,
    investigations: list | None = None,
    advice: list | None = None,
    follow_up: str = "",
    doctor_notes: str = "",
) -> dict:
    """Create a new prescription dict with all required fields."""
    return {
        "consultation_id": f"CONS-{uuid.uuid4().hex[:8].upper()}",
        "doctor_id": doctor_id,
        "patient": patient or {
            "name": "",
            "age": None,
            "sex": "",
            "patient_id": "",
        },
        "complaints": complaints or [],
        "diagnosis": diagnosis or [],
        "medications": medications or [],
        "investigations": investigations or [],
        "advice": advice or [],
        "follow_up": follow_up,
        "doctor_notes": doctor_notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "draft",
    }


def update_status(prescription: dict, status: str) -> dict:
    """Update prescription status: draft → confirmed → final."""
    valid = ("draft", "confirmed", "final")
    if status not in valid:
        raise ValueError(f"Status must be one of {valid}")
    prescription["status"] = status
    return prescription
