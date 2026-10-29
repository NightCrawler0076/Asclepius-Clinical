"""
Unit and regression tests for Phonetic & Fuzzy Speech Error Detection,
Generic Noise Filtering, and Frequency/Duration Normalization.
Run: python -m pytest tests/test_phonetic_fuzzy.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinical.normalizer import soundex, phonetic_key, fuzzy_match_drug, normalize_medication, normalize_entities
from clinical.extractor import extract, _normalize_frequency, _normalize_duration


def test_soundex_encoding():
    assert soundex("Paracetamol") == soundex("Paracetemol")
    assert soundex("Crocin") == soundex("Krocin")
    assert soundex("Dolo") == soundex("Dollo")


def test_phonetic_key_encoding():
    assert phonetic_key("Ciprofloxacin") == phonetic_key("Siprofloxacin")
    assert phonetic_key("Flagyl") == phonetic_key("Flajyl")
    assert phonetic_key("Phospha") == phonetic_key("Fosfa")


def test_exact_drug_matches():
    match = fuzzy_match_drug("paracetamol")
    assert match is not None
    assert match["normalized"] == "Paracetamol"
    assert match["confidence"] == 1.0
    assert match["match_type"] == "exact"

    match_brand = fuzzy_match_drug("dolo")
    assert match_brand["normalized"] == "Paracetamol"


def test_generic_non_medicinal_rejection():
    # Words like "even if", "rest", "food", "water", "care" should NOT be matched as medicines
    non_medicines = [
        "even if", "even", "if", "rest", "food", "water", "meals", "care", "it", "this",
        "morning", "night", "day", "properly", "regularly", "plenty of"
    ]
    for non_med in non_medicines:
        res = fuzzy_match_drug(non_med)
        assert res is None, f"Non-medicinal word '{non_med}' should be rejected, but got {res}"


def test_phonetic_and_fuzzy_corrections():
    test_cases = [
        ("parasitamol", "Paracetamol"),
        ("paracetemol", "Paracetamol"),
        ("amoxacillin", "Amoxicillin"),
        ("amoxi", "Amoxicillin"),
        ("azithro", "Azithromycin"),
        ("pantaprazole", "Pantoprazole"),
        ("pantoprazol", "Pantoprazole"),
        ("sitrizine", "Cetirizine"),
        ("setrizine", "Cetirizine"),
        ("ibuprufen", "Ibuprofen"),
        ("metforman", "Metformin"),
        ("augmantin", "Amoxicillin + Clavulanic Acid"),
        ("krocin", "Paracetamol"),
        ("zerodol", "Aceclofenac"),
        ("pan d", "Pantoprazole + Domperidone"),
        ("telma", "Telmisartan"),
    ]

    for noisy_input, expected_canonical in test_cases:
        res = fuzzy_match_drug(noisy_input)
        assert res is not None, f"Failed to match {noisy_input}"
        assert res["normalized"] == expected_canonical, f"Expected {expected_canonical} for '{noisy_input}', got {res['normalized']}"
        assert res["confidence"] >= 0.70


def test_frequency_normalization():
    assert "BD" in _normalize_frequency("take two times a day")
    assert "TID" in _normalize_frequency("1-1-1")
    assert "OD" in _normalize_frequency("once daily in the morning")
    assert "SOS" in _normalize_frequency("take if needed for pain")
    assert "Bedtime" in _normalize_frequency("at bed time")


def test_duration_normalization():
    assert _normalize_duration("take for 5 days") == "5 days"
    assert _normalize_duration("continue for two weeks") == "2 weeks"
    assert _normalize_duration("for 1 month") == "1 month"
    assert _normalize_duration("course of three days") == "3 days"


def test_extract_no_sickness_duration_in_complaints():
    text = "Patient has high fever for 3 days and severe cough since 1 week. Give Paracetamol 500mg TID for 5 days."
    res = extract(text)
    
    # Complaints should NOT have sickness duration listed
    complaint_names = [c["name"] for c in res["complaints"]]
    assert "fever" in complaint_names
    assert "cough" in complaint_names
    for c in res["complaints"]:
        assert c["duration"] == "", "Sickness duration should not be listed in complaints"

    # Medication duration MUST be preserved
    assert len(res["medications"]) == 1
    med = res["medications"][0]
    assert med["name"] == "Paracetamol"
    assert "500" in med["dose"]
    assert "TID" in med["frequency"]
    assert med["duration"] == "5 days"


def test_extract_rejects_generic_noise_in_transcript():
    text = "Patient has acidity. Take rest and drink water. Take even if nausea occurs. Prescribe Pantoprazole 40mg once daily for 14 days."
    res = extract(text)

    med_names = [m["name"] for m in res["medications"]]
    assert "Pantoprazole" in med_names
    assert "Even If" not in med_names
    assert "Rest" not in med_names
    assert "Water" not in med_names
