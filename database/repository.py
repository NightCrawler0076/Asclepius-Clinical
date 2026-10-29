"""
Database repository — CRUD operations for all entities.
"""

import json
import uuid
from datetime import datetime, timezone

from database.models import get_connection


# ── Doctors ────────────────────────────────────────────────

def create_doctor(name: str, specialty: str = "", clinic_name: str = "", phone: str = "") -> dict:
    doctor_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    connection = get_connection()
    connection.execute(
        "INSERT INTO doctors (id, name, specialty, clinic_name, phone) VALUES (?, ?, ?, ?, ?)",
        (doctor_id, name, specialty, clinic_name, phone),
    )
    connection.commit()
    connection.close()
    return {"id": doctor_id, "name": name, "specialty": specialty}


def get_doctor(doctor_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    connection.close()
    return dict(row) if row else None


def list_doctors() -> list[dict]:
    connection = get_connection()
    rows = connection.execute("SELECT * FROM doctors ORDER BY created_at DESC").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def delete_doctor(doctor_id: str) -> bool:
    connection = get_connection()
    cursor = connection.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted


# ── Patients ───────────────────────────────────────────────

def create_patient(name: str, age: int | None = None, sex: str = "", phone: str = "") -> dict:
    patient_id = f"PAT-{uuid.uuid4().hex[:8].upper()}"
    connection = get_connection()
    connection.execute(
        "INSERT INTO patients (id, name, age, sex, phone) VALUES (?, ?, ?, ?, ?)",
        (patient_id, name, age, sex, phone),
    )
    connection.commit()
    connection.close()
    return {"id": patient_id, "name": name, "age": age, "sex": sex}


def get_patient(patient_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    connection.close()
    return dict(row) if row else None


def list_patients() -> list[dict]:
    connection = get_connection()
    rows = connection.execute("SELECT * FROM patients ORDER BY created_at DESC").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def delete_patient(patient_id: str) -> bool:
    connection = get_connection()
    cursor = connection.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted


# ── Consultations ──────────────────────────────────────────

def create_consultation(doctor_id: str, patient_id: str = None, audio_path: str = "") -> dict:
    consultation_id = f"CONS-{uuid.uuid4().hex[:8].upper()}"
    connection = get_connection()
    connection.execute(
        "INSERT INTO consultations (id, doctor_id, patient_id, audio_path) VALUES (?, ?, ?, ?)",
        (consultation_id, doctor_id, patient_id, audio_path),
    )
    connection.commit()
    connection.close()
    return {"id": consultation_id, "doctor_id": doctor_id, "patient_id": patient_id}


def get_consultation(consultation_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute("SELECT * FROM consultations WHERE id = ?", (consultation_id,)).fetchone()
    connection.close()
    return dict(row) if row else None


def list_consultations(doctor_id: str = None) -> list[dict]:
    connection = get_connection()
    if doctor_id:
        rows = connection.execute(
            "SELECT * FROM consultations WHERE doctor_id = ? ORDER BY created_at DESC",
            (doctor_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM consultations ORDER BY created_at DESC"
        ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


# ── Transcripts ────────────────────────────────────────────

def save_transcript(consultation_id: str, text: str, language: str = "",
                    model_used: str = "", segments: list | None = None) -> int:
    connection = get_connection()
    cursor = connection.execute(
        "INSERT INTO transcripts (consultation_id, text, language, model_used, segments_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (consultation_id, text, language, model_used, json.dumps(segments or [])),
    )
    connection.commit()
    transcript_id = cursor.lastrowid
    connection.close()
    return transcript_id


def get_transcript(consultation_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM transcripts WHERE consultation_id = ? ORDER BY created_at DESC LIMIT 1",
        (consultation_id,),
    ).fetchone()
    connection.close()
    if row:
        transcript_record = dict(row)
        transcript_record["segments"] = json.loads(transcript_record.get("segments_json", "[]"))
        return transcript_record
    return None


# ── Prescriptions ──────────────────────────────────────────

def save_prescription(consultation_id: str, prescription_data: dict, status: str = "draft") -> int:
    connection = get_connection()
    cursor = connection.execute(
        "INSERT INTO prescriptions (consultation_id, data_json, status) VALUES (?, ?, ?)",
        (consultation_id, json.dumps(prescription_data, ensure_ascii=False), status),
    )
    connection.commit()
    prescription_id = cursor.lastrowid
    connection.close()
    return prescription_id


def get_prescription(consultation_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM prescriptions WHERE consultation_id = ? ORDER BY created_at DESC LIMIT 1",
        (consultation_id,),
    ).fetchone()
    connection.close()
    if row:
        prescription_record = dict(row)
        prescription_record["data"] = json.loads(prescription_record.get("data_json", "{}"))
        return prescription_record
    return None


def update_prescription(prescription_id: int, prescription_data: dict, status: str = "draft") -> None:
    connection = get_connection()
    confirmed_at = datetime.now(timezone.utc).isoformat() if status == "confirmed" else None
    connection.execute(
        "UPDATE prescriptions SET data_json = ?, status = ?, confirmed_at = ? WHERE id = ?",
        (json.dumps(prescription_data, ensure_ascii=False), status, confirmed_at, prescription_id),
    )
    connection.commit()
    connection.close()


def get_prescription_by_id(prescription_id: int) -> dict | None:
    """Fetch a prescription row by its primary key (id)."""
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM prescriptions WHERE id = ?", (prescription_id,)
    ).fetchone()
    connection.close()
    if row:
        prescription_record = dict(row)
        prescription_record["data"] = json.loads(prescription_record.get("data_json", "{}"))
        return prescription_record
    return None


def list_all_prescriptions() -> list[dict]:
    """List all saved prescriptions with doctor and patient metadata, ordered by latest."""
    connection = get_connection()
    query = """
        SELECT 
            p.id,
            p.consultation_id,
            p.data_json,
            p.status,
            p.created_at,
            p.confirmed_at,
            c.doctor_id,
            c.patient_id,
            d.name AS doctor_name,
            d.specialty AS doctor_specialty,
            pt.name AS patient_name,
            pt.age AS patient_age,
            pt.sex AS patient_sex
        FROM prescriptions p
        LEFT JOIN consultations c ON p.consultation_id = c.id
        LEFT JOIN doctors d ON c.doctor_id = d.id
        LEFT JOIN patients pt ON c.patient_id = pt.id
        ORDER BY p.id DESC
    """
    rows = connection.execute(query).fetchall()
    connection.close()
    
    prescriptions_list = []
    for row in rows:
        item = dict(row)
        try:
            item["data"] = json.loads(item.get("data_json") or "{}")
        except Exception:
            item["data"] = {}
        prescriptions_list.append(item)
    return prescriptions_list


def delete_prescription(prescription_id: int) -> bool:
    """Delete a prescription record by its ID."""
    connection = get_connection()
    cursor = connection.execute("DELETE FROM prescriptions WHERE id = ?", (prescription_id,))
    connection.commit()
    is_deleted = cursor.rowcount > 0
    connection.close()
    return is_deleted
