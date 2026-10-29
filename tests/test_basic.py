"""
Basic smoke tests for the modular structure.
Run: python -m pytest tests/ -v
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config_imports():
    from config import SAMPLE_RATE, MODEL_SIZES, DB_PATH
    assert SAMPLE_RATE == 16000
    assert "base" in MODEL_SIZES
    assert DB_PATH.endswith("database.sqlite")


def test_database_init():
    from database.models import init_db, get_connection
    init_db()
    conn = get_connection()
    # Check tables exist
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t["name"] for t in tables]
    conn.close()
    assert "doctors" in table_names
    assert "patients" in table_names
    assert "consultations" in table_names
    assert "prescriptions" in table_names
    assert "sync_queue" in table_names


def test_doctor_crud():
    from database.models import init_db
    from database.repository import create_doctor, get_doctor, list_doctors
    init_db()
    doc = create_doctor("Dr. Test", specialty="General")
    assert doc["id"].startswith("DOC-")
    assert doc["name"] == "Dr. Test"

    fetched = get_doctor(doc["id"])
    assert fetched is not None
    assert fetched["name"] == "Dr. Test"

    doctors = list_doctors()
    assert any(d["id"] == doc["id"] for d in doctors)


def test_patient_crud():
    from database.models import init_db
    from database.repository import create_patient, get_patient
    init_db()
    pat = create_patient("Test Patient", age=30, sex="M")
    assert pat["id"].startswith("PAT-")

    fetched = get_patient(pat["id"])
    assert fetched is not None
    assert fetched["age"] == 30


def test_prescription_schema():
    from prescription.schema import new_prescription
    rx = new_prescription(doctor_id="DOC-TEST")
    assert rx["doctor_id"] == "DOC-TEST"
    assert rx["status"] == "draft"
    assert rx["consultation_id"].startswith("CONS-")
    assert isinstance(rx["medications"], list)


def test_clinical_extractor():
    from clinical.extractor import extract
    text = "Patient has fever for 3 days. Give paracetamol 500 mg three times a day for 5 days."
    result = extract(text.lower())
    assert len(result["complaints"]) > 0
    assert any(c["name"] == "fever" for c in result["complaints"])


def test_prescription_generator():
    from database.models import init_db
    init_db()
    from prescription.generator import generate_from_transcript
    rx = generate_from_transcript(
        "Patient has headache. Give ibuprofen 400mg.",
        doctor_id="DOC-TEST",
    )
    assert rx["status"] == "draft"
    assert rx["doctor_id"] == "DOC-TEST"


def test_clinical_rules():
    from clinical.rules import validate_prescription
    # Empty prescription should warn
    warnings = validate_prescription({"medications": []})
    assert any(w["level"] == "warning" for w in warnings)


def test_normalizer():
    from clinical.normalizer import normalize_medication
    result = normalize_medication("paracetamol")
    assert result["normalized"] == "Paracetamol"
    assert result["confidence"] == 1.0
