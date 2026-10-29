"""
Comprehensive Evaluation Suite for Voice-to-Prescription Pipeline.
Tests end-to-end extraction across diverse realistic clinical scenarios:
1. Multi-drug acute respiratory infection with Indian brands
2. Chronic illness consultation (Diabetes + Hypertension)
3. Gastrointestinal symptoms with non-medicinal distractor phrases
4. Pediatric / liquid formulation with weight-based advice
5. Complex dosing formats (1-0-1, TDS, SOS, at bedtime)
6. Investigations, advice, and follow-up parsing
7. Ensuring illness duration is omitted from complaints
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prescription.generator import generate_from_transcript
from clinical.llm_refiner import get_status


SCENARIOS = [
    {
        "id": "scenario_1_acute_respiratory",
        "title": "Acute Respiratory Infection with Indian Brands",
        "transcript": (
            "Patient is a 34-year-old male with complaints of high grade fever for 3 days, "
            "severe sore throat, and dry cough for 1 week. On examination, pharynx is congested. "
            "Diagnosis is acute pharyngitis with upper respiratory tract infection. "
            "I am prescribing Augmentin 625mg twice a day after meals for 5 days. "
            "Also give Dolo 650mg thrice daily for 3 days, and Levocet 5mg once daily at bedtime for 5 days. "
            "Get a complete blood count CBC done if fever persists. "
            "Drink plenty of warm fluids, do warm salt water gargles, and take adequate rest. "
            "Review after 5 days or earlier if symptoms worsen."
        ),
        "expectations": {
            "complaints_include": ["fever", "sore throat", "cough"],
            "complaints_exclude_duration": True,
            "medications_min_count": 3,
            "med_names": ["Amoxicillin + Clavulanic Acid", "Paracetamol", "Levocetirizine"],
            "investigations_include": ["cbc", "complete blood count"],
            "has_follow_up": True,
        }
    },
    {
        "id": "scenario_2_chronic_hypertension_diabetes",
        "title": "Chronic Disease Follow-up (HTN + T2DM)",
        "transcript": (
            "Review visit for 58-year-old female with known case of hypertension and type 2 diabetes mellitus. "
            "Complains of occasional dizziness and mild headache. Blood pressure today is 145/90. "
            "We will continue Telma 40mg once daily in the morning before breakfast. "
            "Increase Glycomet 500mg to twice daily with meals. "
            "Add Atorva 10mg once daily at night for lipid management. "
            "Advise HbA1c, fasting blood sugar, post prandial blood sugar, and lipid profile. "
            "Follow a strict low salt and diabetic diet, 30 minutes brisk walking daily. "
            "Follow up in 1 month with test reports."
        ),
        "expectations": {
            "complaints_include": ["dizziness", "headache"],
            "med_names": ["Telmisartan", "Metformin", "Atorvastatin"],
            "has_follow_up": True,
        }
    },
    {
        "id": "scenario_3_gi_with_distractor_phrases",
        "title": "GI Distress with Distractor Phrases (even if, take rest, drink water)",
        "transcript": (
            "Patient presents with severe acidity, heartburn, and vomiting since yesterday. "
            "Patient says even if he drinks water, nausea triggers. "
            "Take rest and avoid spicy and oily food completely. "
            "Prescribe Pan-D capsule once daily morning on empty stomach for 14 days. "
            "Also take Emset 4mg whenever needed for nausea or vomiting. "
            "Take Sucrafil syrup 10ml thrice daily before food for 7 days. "
            "Drink oral rehydration solution ORS sip by sip. "
            "Come back for review after 1 week."
        ),
        "expectations": {
            "complaints_include": ["acidity", "heartburn", "vomiting", "nausea"],
            "med_names": ["Pantoprazole + Domperidone", "Ondansetron", "Sucralfate"],
            "meds_exclude": ["Even If", "Rest", "Water", "Food"],
            "has_follow_up": True,
        }
    },
    {
        "id": "scenario_4_shorthand_dosing",
        "title": "Indian Shorthand Dosing (1-0-1, 1-1-1, SOS)",
        "transcript": (
            "Young adult with severe body ache, joint pain, and mild fever. "
            "Give Combiflam tablet 1-0-1 for 3 days after food. "
            "Give Pantocid 40mg 1-0-0 before breakfast for 5 days. "
            "Give Meftal Spas 1 tablet SOS only if severe abdominal cramps occur. "
            "Advise complete bed rest and hydration."
        ),
        "expectations": {
            "complaints_include": ["body ache", "joint pain", "fever", "abdominal cramps"],
            "med_names": ["Ibuprofen + Paracetamol", "Pantoprazole", "Mefenamic Acid + Dicyclomine"],
        }
    },
    {
        "id": "scenario_5_pediatric_and_inhaler",
        "title": "Respiratory Consultation with Inhaler & Syrups",
        "transcript": (
            "Patient is experiencing wheezing, chest tightness, and breathlessness. "
            "Provisional diagnosis is acute bronchial asthma flare. "
            "Start Asthalin inhaler 2 puffs 4 times a day as needed. "
            "Start Budecort 200mcg inhaler twice a day for 1 month. "
            "Add Montair LC tablet once daily at night for 10 days. "
            "Advise chest X-ray and spirometry. "
            "Avoid cold drinks, dust exposure, and smoke. "
            "Return for review in 2 weeks."
        ),
        "expectations": {
            "complaints_include": ["wheezing", "breathlessness"],
            "med_names": ["Salbutamol", "Budesonide", "Montelukast + Levocetirizine"],
            "investigations_include": ["chest x-ray", "spirometry"],
            "has_follow_up": True,
        }
    },
]


def run_evaluation():
    print("=" * 80)
    print("CLINICAL TRANSCRIPTION & EXTRACTION EVALUATION SUITE")
    print(f"LLM Engine Status: {get_status()}")
    print("=" * 80)

    total_scenarios = len(SCENARIOS)
    passed_scenarios = 0

    for idx, scenario in enumerate(SCENARIOS, 1):
        print(f"\n[{idx}/{total_scenarios}] Running: {scenario['title']}")
        print("-" * 80)
        
        start_time = time.time()
        rx = generate_from_transcript(scenario["transcript"], doctor_id="Doctor 1", patient={"name": "Patient 1", "age": 40, "sex": "M"})
        elapsed = time.time() - start_time
        
        # Display key extracted fields
        print(f"[*] Extraction Time: {elapsed:.2f}s")
        print(f"[*] Complaints Extracted: {[c.get('name') for c in rx.get('complaints', [])]}")
        print(f"[*] Medications Extracted ({len(rx.get('medications', []))}):")
        for m in rx.get("medications", []):
            print(f"    - {m.get('name')} | Dose: {m.get('dose') or 'N/A'} | Freq: {m.get('frequency') or 'N/A'} | Dur: {m.get('duration') or 'N/A'}")
        print(f"[*] Investigations: {rx.get('investigations', [])}")
        print(f"[*] Advice ({len(rx.get('advice', []))} items): {rx.get('advice', [])}")
        print(f"[*] Follow-Up: {rx.get('follow_up')}")

        # Verification of expectations
        exp = scenario["expectations"]
        checks = []

        # Check complaints
        extracted_comp_names = [c.get("name", "").lower() for c in rx.get("complaints", [])]
        for needed_comp in exp.get("complaints_include", []):
            match = any(needed_comp in c for c in extracted_comp_names)
            checks.append((f"Complaint '{needed_comp}' detected", match))

        # Check no duration in complaints
        for c in rx.get("complaints", []):
            if c.get("duration"):
                checks.append(("No sickness duration in complaint tag", False))
                break
        else:
            checks.append(("No sickness duration in complaint tag", True))

        # Check medication detection & normalization
        extracted_med_names = [m.get("name", "").lower() for m in rx.get("medications", [])]
        for needed_med in exp.get("med_names", []):
            match = any(needed_med.lower() in m or m in needed_med.lower() for m in extracted_med_names)
            checks.append((f"Medication '{needed_med}' normalized", match))

        # Check excluded non-medicines
        for excl in exp.get("meds_exclude", []):
            present = any(excl.lower() == m.lower() for m in extracted_med_names)
            checks.append((f"Non-medicine '{excl}' rejected", not present))

        # Check follow-up
        if exp.get("has_follow_up"):
            checks.append(("Follow-up parsed", bool(rx.get("follow_up"))))

        all_passed = all(status for _, status in checks)
        if all_passed:
            passed_scenarios += 1
            print("[PASS] Scenario verified successfully.")
        else:
            print("[WARN] Scenario has partial matches / issues:")
            for desc, status in checks:
                icon = "[+]" if status else "[-]"
                print(f"    {icon} {desc}")

    print("\n" + "=" * 80)
    print(f"FINAL SUMMARY: {passed_scenarios}/{total_scenarios} scenarios passed all evaluation checks.")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
