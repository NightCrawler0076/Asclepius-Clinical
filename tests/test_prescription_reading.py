"""
Doctor Prescription Reading — Test Transcripts for Expanded Pipeline
====================================================================
These realistic doctor transcripts exercise ALL the newly added features:
- 428 medicine catalog with route & instructions
- 40+ brand->generic hints in LLM prompt
- 4 few-shot examples
- ~40 new diagnosis keywords & ~20 new symptom keywords
- Auto-enrichment of route/instructions from catalog

Usage:
    py tests/test_prescription_reading.py
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prescription.generator import generate_from_transcript
from clinical.llm_refiner import get_status


# ---------------------------------------------------------------
# TRANSCRIPTS - realistic doctor dictation / conversations
# ---------------------------------------------------------------

TRANSCRIPTS = [
    {
        "id": "rx_1_fever_pain",
        "title": "1. Acute Fever & Body Pain - Common OPD Case",
        "transcript": (
            "Patient is a 28-year-old male, presenting with high grade fever for 3 days, "
            "severe body ache, headache, and sore throat. "
            "On examination, pharynx is congested, no rash. "
            "Diagnosis is viral fever with acute pharyngitis. "
            "Prescribe Dolo 650mg thrice daily after food for 3 days. "
            "Combiflam tablet 1 tablet twice daily after food for 3 days for body pain. "
            "Azee 500mg once daily for 3 days. "
            "Levocet 5mg once daily at bedtime for 5 days for throat congestion. "
            "Pan 40mg once daily before breakfast for 5 days for gastric protection. "
            "Get CBC, ESR, and dengue NS1 antigen done. "
            "Advise plenty of oral fluids, rest, and light diet. "
            "Follow up after 3 days or earlier if fever does not subside."
        ),
        "expect_meds": ["Dolo", "Combiflam", "Azee", "Levocet", "Pan"],
        "expect_dx": ["viral fever", "pharyngitis"],
        "expect_sx": ["fever", "body ache", "headache", "sore throat"],
    },
    {
        "id": "rx_2_chronic_diabetes_hypertension",
        "title": "2. Chronic Disease Follow-Up - Diabetes + Hypertension + Dyslipidemia",
        "transcript": (
            "58-year-old female, known case of type 2 diabetes mellitus, hypertension, "
            "and dyslipidemia. On regular follow-up. "
            "Complains of occasional dizziness and tingling in both feet. "
            "Blood pressure is 148 over 92 today. "
            "Continue Telma 40mg once daily in the morning. "
            "Continue Glycomet GP 500mg/2mg twice daily, one before breakfast and one before dinner. "
            "Continue Atorva 20mg once daily at bedtime. "
            "Add Ecosprin 75mg once daily after lunch. "
            "For the tingling, start Methylcobalamin 1500mcg once daily after food. "
            "Shelcal 500 once daily after lunch for calcium. "
            "Advise HbA1c, fasting blood sugar, post prandial blood sugar, lipid profile, "
            "serum creatinine, and urine microalbumin. "
            "Strict diabetic diet, reduce salt intake, 30 minutes brisk walking daily. "
            "Review in 3 months with reports."
        ),
        "expect_meds": ["Telma", "Glycomet", "Atorva", "Ecosprin", "Methylcobalamin", "Shelcal"],
        "expect_dx": ["diabetes", "hypertension", "dyslipidemia"],
        "expect_sx": ["dizziness", "tingling"],
    },
    {
        "id": "rx_3_pediatric_ent",
        "title": "3. Pediatric ENT - Otitis Media with Nasal Congestion",
        "transcript": (
            "5-year-old child brought by mother with complaints of ear pain, "
            "ear discharge from the left ear for 2 days, blocked nose, and mild fever. "
            "On examination, tympanic membrane is congested. "
            "Diagnosis is acute otitis media. "
            "Prescribe Cefpodoxime syrup 100mg twice daily after food for 5 days. "
            "Combiflam drops for pain SOS, give as needed when child cries with pain. "
            "Otrivin nasal drops, 1 drop in each nostril twice daily for 3 days. "
            "Moxifloxacin ear drops, 2 drops in left ear thrice daily for 5 days. "
            "Keep the ear dry, no swimming, no water entry into the ear. "
            "Follow up in 5 days."
        ),
        "expect_meds": ["Cefpodoxime", "Combiflam", "Otrivin", "Moxifloxacin"],
        "expect_dx": ["otitis media"],
        "expect_sx": ["ear pain", "ear discharge", "fever"],
    },
    {
        "id": "rx_4_gi_distress",
        "title": "4. GI Distress - Acidity + Vomiting + Diarrhea",
        "transcript": (
            "32-year-old female presenting with severe acidity, heartburn, "
            "nausea, vomiting, and loose motions for the past 2 days. "
            "Patient also reports abdominal cramps and loss of appetite. "
            "Diagnosis is acute gastroenteritis. "
            "Prescribe Pan-D capsule once daily on empty stomach in the morning for 14 days. "
            "Emset 4mg SOS for vomiting, maximum 3 times a day. "
            "Norflox-TZ one tablet twice daily after food for 5 days. "
            "Econorm sachet one sachet twice daily for 5 days. "
            "Drink ORS solution sip by sip throughout the day. "
            "Avoid spicy, oily, and outside food completely. "
            "Stool routine and microscopy if diarrhea persists beyond 3 days. "
            "Follow up in 1 week."
        ),
        "expect_meds": ["Pan-D", "Emset", "Norflox-TZ"],
        "expect_dx": ["gastroenteritis"],
        "expect_sx": ["acidity", "heartburn", "nausea", "vomiting", "loose motions", "abdominal cramps", "loss of appetite"],
    },
    {
        "id": "rx_5_orthopedic_pain",
        "title": "5. Orthopedic - Cervical Spondylosis + Frozen Shoulder",
        "transcript": (
            "45-year-old male, IT professional, presenting with neck pain radiating to the right arm "
            "for 1 month. Also has shoulder pain and stiffness in the right shoulder. "
            "Cannot raise arm above head. Numbness and tingling in the fingers. "
            "X-ray cervical spine shows C5-C6 disc space narrowing. "
            "Diagnosis is cervical spondylosis with right frozen shoulder. "
            "Prescribe Zerodol SP one tablet twice daily after food for 7 days. "
            "Pregabalin 75mg once daily at bedtime for 2 weeks for nerve pain. "
            "Thiocolchicoside 4mg twice daily for 5 days as muscle relaxant. "
            "Apply Voveran gel locally over neck and shoulder three times a day. "
            "Shelcal 500 once daily after food. "
            "Calcirol sachet 60000 IU once weekly for 8 weeks for vitamin D. "
            "Advise MRI cervical spine if symptoms do not improve. "
            "Refer for physiotherapy, 10 sessions. "
            "Avoid prolonged sitting, use cervical collar while working. "
            "Review in 2 weeks."
        ),
        "expect_meds": ["Zerodol", "Pregabalin", "Thiocolchicoside", "Voveran", "Shelcal", "Calcirol"],
        "expect_dx": ["cervical spondylosis", "frozen shoulder"],
        "expect_sx": ["neck pain", "shoulder pain", "numbness", "tingling"],
    },
    {
        "id": "rx_6_tb_treatment",
        "title": "6. Pulmonary TB - Anti-Tubercular Treatment Initiation",
        "transcript": (
            "35-year-old male, laborer, presenting with persistent cough for 6 weeks, "
            "blood in sputum, night sweats, weight loss, and loss of appetite. "
            "Chest X-ray shows right upper lobe infiltrate with cavity. "
            "Sputum AFB smear is positive. Gene Xpert confirms Mycobacterium tuberculosis, "
            "rifampicin sensitive. "
            "Diagnosis is pulmonary tuberculosis, sputum positive, new case. "
            "Start AKT-4, that is the 4 drug fixed dose combination, "
            "4 tablets once daily on empty stomach in the morning for intensive phase 2 months. "
            "Also give Pyridoxine 40mg once daily to prevent isoniazid neuropathy. "
            "Tab Shelcal 500 once daily. "
            "Advise sputum AFB follow up at 2 months, liver function test, "
            "serum creatinine and complete blood count at baseline. "
            "Maintain cough hygiene, wear mask, well ventilated room. "
            "High protein diet, eggs, milk, pulses. "
            "Follow up every 2 weeks in intensive phase, monthly thereafter."
        ),
        "expect_meds": ["AKT-4", "Pyridoxine", "Shelcal"],
        "expect_dx": ["tuberculosis"],
        "expect_sx": ["cough", "blood in sputum", "night sweats", "weight loss", "loss of appetite"],
    },
]


# ---------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------

def print_separator(char="=", width=90):
    print(char * width)


def run_all():
    print_separator()
    print("  DOCTOR PRESCRIPTION READING - EXPANDED PIPELINE VERIFICATION")
    print(f"  LLM Status: {get_status()}")
    print_separator()

    total = len(TRANSCRIPTS)
    passed = 0

    for i, scenario in enumerate(TRANSCRIPTS, 1):
        print(f"\n{'='*90}")
        print(f"  [{i}/{total}] {scenario['title']}")
        print(f"{'='*90}")
        print(f"\n  Transcript (first 200 chars):")
        print(f"  \"{scenario['transcript'][:200]}...\"")

        start = time.time()
        rx = generate_from_transcript(
            scenario["transcript"],
            doctor_id="Doctor 1",
            patient={"name": "Patient 1", "age": 40, "sex": "M"},
        )
        elapsed = time.time() - start

        print(f"\n  Extraction time: {elapsed:.2f}s")

        # Complaints
        comp_names = [c.get("name", "") for c in rx.get("complaints", [])]
        print(f"\n  COMPLAINTS: {comp_names}")

        # Diagnosis
        print(f"  DIAGNOSIS:  {rx.get('diagnosis', [])}")

        # Medications - the money table
        meds = rx.get("medications", [])
        print(f"\n  MEDICATIONS ({len(meds)}):")
        print(f"  {'Name':<30} {'Dose':<12} {'Freq':<8} {'Duration':<12} {'Route':<14} {'Instructions'}")
        print(f"  {'-'*30} {'-'*12} {'-'*8} {'-'*12} {'-'*14} {'-'*30}")
        for m in meds:
            print(f"  {m.get('name',''):<30} {m.get('dose',''):<12} {m.get('frequency',''):<8} "
                  f"{m.get('duration',''):<12} {m.get('route',''):<14} {m.get('instructions','')}")

        # Investigations
        print(f"\n  INVESTIGATIONS: {rx.get('investigations', [])}")

        # Advice
        print(f"  ADVICE:         {rx.get('advice', [])}")

        # Follow-up
        print(f"  FOLLOW-UP:      {rx.get('follow_up', '')}")

        # -- Quick validation --
        issues = []

        # Check expected symptoms
        comp_lower = [c.lower() for c in comp_names]
        for sx in scenario.get("expect_sx", []):
            if not any(sx.lower() in c for c in comp_lower):
                issues.append(f"Missing symptom: {sx}")

        # Check expected diagnoses
        dx_lower = [d.lower() for d in rx.get("diagnosis", [])]
        dx_joined = " ".join(dx_lower)
        for dx in scenario.get("expect_dx", []):
            if dx.lower() not in dx_joined:
                issues.append(f"Missing diagnosis: {dx}")

        # Check expected medicines (by brand name anywhere in med names)
        med_lower = [m.get("name", "").lower() for m in meds]
        med_joined = " ".join(med_lower)
        for med_name in scenario.get("expect_meds", []):
            if med_name.lower() not in med_joined:
                issues.append(f"Missing medication: {med_name}")

        # Check route/instructions enrichment
        meds_missing_route = [m["name"] for m in meds if not m.get("route")]
        if meds_missing_route:
            issues.append(f"Missing route for: {meds_missing_route}")

        if issues:
            print(f"\n  [!] ISSUES ({len(issues)}):")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print(f"\n  [OK] All checks passed!")
            passed += 1

    print(f"\n{'='*90}")
    print(f"  FINAL: {passed}/{total} scenarios passed all checks")
    print(f"{'='*90}")


if __name__ == "__main__":
    run_all()
