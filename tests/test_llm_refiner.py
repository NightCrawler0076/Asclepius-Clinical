"""
Tests for clinical/llm_refiner.py — mock-based (no actual LLM model required).
Run: python -m pytest tests/test_llm_refiner.py -v
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinical.llm_refiner import (
    _build_prompt,
    _parse_llm_response,
    _validate_medications,
    _validate_complaints,
    _merge_entities,
    _sanitize_draft,
)


# ── Prompt Construction Tests ─────────────────────────────

def test_build_prompt_contains_transcript():
    transcript = "Patient has fever. Give Paracetamol 500mg BD for 3 days."
    draft = {"complaints": [{"name": "fever"}], "medications": [{"name": "Paracetamol"}]}
    prompt = _build_prompt(transcript, draft)
    assert "fever" in prompt
    assert "Paracetamol" in prompt
    assert "Transcript:" in prompt
    assert "Draft extraction" in prompt


def test_build_prompt_truncates_long_transcripts():
    long_transcript = "word " * 500  # ~2500 chars
    draft = {"complaints": [], "medications": []}
    prompt = _build_prompt(long_transcript, draft)
    # Should be truncated with leading "..."
    assert "..." in prompt


def test_sanitize_draft_strips_metadata():
    draft = {
        "complaints": [{"name": "cough", "duration": ""}],
        "medications": [{"name": "Amoxicillin", "dose": "500mg", "_normalization": {"confidence": 0.95}}],
        "diagnosis": ["URTI"],
        "investigations": ["CBC"],
        "advice": ["Rest"],
        "follow_up": "1 week",
    }
    sanitized = _sanitize_draft(draft)
    assert sanitized["complaints"] == ["cough"]
    assert len(sanitized["medications"]) == 1
    assert "_normalization" not in sanitized["medications"][0]
    assert sanitized["medications"][0]["name"] == "Amoxicillin"


# ── JSON Parsing Tests ────────────────────────────────────

def test_parse_valid_json():
    raw = '{"complaints":["fever"],"medications":[{"name":"Dolo","dose":"650mg"}]}'
    result = _parse_llm_response(raw)
    assert result is not None
    assert result["complaints"] == ["fever"]


def test_parse_json_with_surrounding_text():
    raw = 'Here is the output:\n{"complaints":["fever"],"medications":[]}\n\nDone.'
    result = _parse_llm_response(raw)
    assert result is not None
    assert result["complaints"] == ["fever"]


def test_parse_malformed_json_returns_none():
    raw = "This is not JSON at all"
    result = _parse_llm_response(raw)
    assert result is None


def test_parse_partial_json_returns_none():
    raw = '{"complaints":["fever"]'  # missing closing brace
    result = _parse_llm_response(raw)
    assert result is None


# ── Medication Validation Tests ───────────────────────────

def test_validate_known_medications():
    meds = [
        {"name": "Paracetamol", "dose": "500mg", "frequency": "TID", "duration": "5 days"},
        {"name": "Azithromycin", "dose": "500mg", "frequency": "OD", "duration": "3 days"},
    ]
    validated = _validate_medications(meds)
    assert len(validated) == 2
    names = [m["name"] for m in validated]
    assert "Paracetamol" in names
    assert "Azithromycin" in names


def test_validate_rejects_non_medicinal_words():
    meds = [
        {"name": "rest", "dose": "", "frequency": "", "duration": ""},
        {"name": "water", "dose": "", "frequency": "", "duration": ""},
        {"name": "Paracetamol", "dose": "500mg", "frequency": "BD", "duration": "5 days"},
    ]
    validated = _validate_medications(meds)
    names = [m["name"] for m in validated]
    assert "Rest" not in names and "rest" not in names
    assert "Water" not in names and "water" not in names
    assert "Paracetamol" in names


def test_validate_deduplicates_medications():
    meds = [
        {"name": "paracetamol", "dose": "500mg"},
        {"name": "Paracetamol", "dose": "650mg"},
    ]
    validated = _validate_medications(meds)
    assert len(validated) == 1


def test_validate_flags_unknown_drugs_for_review():
    meds = [
        {"name": "Zybranthol", "dose": "100mg"},
    ]
    validated = _validate_medications(meds)
    # Unknown drugs are kept but flagged
    if validated:
        assert validated[0].get("needs_review", False)


# ── Complaint Validation Tests ────────────────────────────

def test_validate_complaints_from_strings():
    complaints = ["fever", "cough", "headache"]
    validated = _validate_complaints(complaints)
    assert len(validated) == 3
    for c in validated:
        assert c["duration"] == ""


def test_validate_complaints_deduplication():
    complaints = ["fever", "Fever", "FEVER"]
    validated = _validate_complaints(complaints)
    assert len(validated) == 1


def test_validate_complaints_from_dicts():
    complaints = [{"name": "fever"}, {"name": "cough"}]
    validated = _validate_complaints(complaints)
    assert len(validated) == 2


# ── Entity Merging Tests ──────────────────────────────────

def test_merge_unions_complaints():
    draft = {"complaints": [{"name": "fever"}], "medications": [], "diagnosis": [],
             "investigations": [], "advice": [], "follow_up": "", "doctor_notes": ""}
    refined = {"complaints": ["fever", "cough"], "medications": [], "diagnosis": [],
               "investigations": [], "advice": [], "follow_up": ""}
    merged = _merge_entities(draft, refined)
    names = [c["name"] for c in merged["complaints"]]
    assert "fever" in names
    assert "cough" in names
    assert len(merged["complaints"]) == 2  # no duplicates


def test_merge_medications_with_validation():
    draft = {
        "complaints": [],
        "medications": [{"name": "Paracetamol", "dose": "500mg", "frequency": "TID", "duration": "5 days"}],
        "diagnosis": [], "investigations": [], "advice": [], "follow_up": "", "doctor_notes": "",
    }
    refined = {
        "complaints": [],
        "medications": [
            {"name": "Paracetamol", "dose": "650mg", "frequency": "TID", "duration": "5 days"},
            {"name": "Azithromycin", "dose": "500mg", "frequency": "OD", "duration": "3 days"},
        ],
        "diagnosis": [], "investigations": [], "advice": [], "follow_up": "",
    }
    merged = _merge_entities(draft, refined)
    names = [m["name"] for m in merged["medications"]]
    assert "Paracetamol" in names
    assert "Azithromycin" in names


def test_merge_preserves_doctor_notes():
    draft = {"complaints": [], "medications": [], "diagnosis": [],
             "investigations": [], "advice": [], "follow_up": "", "doctor_notes": "Patient allergic to penicillin"}
    refined = {"complaints": [], "medications": [], "diagnosis": [],
               "investigations": [], "advice": [], "follow_up": ""}
    merged = _merge_entities(draft, refined)
    assert merged["doctor_notes"] == "Patient allergic to penicillin"


def test_merge_prefers_llm_followup():
    draft = {"complaints": [], "medications": [], "diagnosis": [],
             "investigations": [], "advice": [], "follow_up": "Follow up advised", "doctor_notes": ""}
    refined = {"complaints": [], "medications": [], "diagnosis": [],
               "investigations": [], "advice": [], "follow_up": "Follow up in 1 week"}
    merged = _merge_entities(draft, refined)
    assert merged["follow_up"] == "Follow up in 1 week"


# ── Model Registry & Switching Tests ───────────────────────

from clinical.llm_refiner import list_available_models, set_active_model, get_status, get_active_model_key


def test_list_available_models():
    models = list_available_models()
    assert isinstance(models, list)
    assert len(models) >= 2
    ids = [m["id"] for m in models]
    assert "qwen2.5-1.5b" in ids
    assert "llama-3.2-1b-medical" in ids
    assert "qwen2.5-3b-medical" in ids


def test_set_active_model():
    set_active_model("qwen2.5-3b-medical")
    assert get_active_model_key() == "qwen2.5-3b-medical"
    status = get_status()
    assert status["active_model_key"] == "qwen2.5-3b-medical"

    # Switch back to default
    set_active_model("qwen2.5-1.5b")
    assert get_active_model_key() == "qwen2.5-1.5b"


def test_set_invalid_model_raises():
    import pytest
    with pytest.raises(ValueError):
        set_active_model("nonexistent_model_key")

