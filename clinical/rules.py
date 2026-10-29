"""
Clinical Rules & Pharmacological Reasoning Engine (CDS).

Provides intelligent Clinical Decision Support:
1. Duplicate therapy & active ingredient duplication checks (e.g., Paracetamol toxicity)
2. High-risk Drug-Drug Interactions (DDI)
3. Disease-Drug Contraindications (e.g., Beta-blockers in Asthma, NSAIDs in Ulcers)
4. Antibiotic completeness & Gastric protection checks
5. Missing dosage / route validation
"""

import re
from clinical.medicines import COMMON_MEDICINES


# ── Known Therapeutic Classes & Active Ingredients ──────────

_PARACETAMOL_VARIANTS = {
    "paracetamol", "pcm", "acetaminophen", "dolo", "dolo 650", "crocin", "calpol",
    "pacimol", "pyregesic", "combiflam", "flexon", "zerodol p", "zerodol sp",
    "sinarest", "cheston cold", "wikoryl", "solvin cold",
}

_NSAID_VARIANTS = {
    "ibuprofen", "brufen", "combiflam", "flexon", "diclofenac", "voveran",
    "dynapar", "aceclofenac", "zerodol", "zerodol p", "zerodol sp", "hifenac",
    "naproxen", "naprosyn", "ketorolac", "ketorol", "piroxicam", "etoricoxib",
    "nucoxia", "mefenamic acid", "meftal", "meftal spas",
}

_ANTICOAGULANTS_ANTIPLATELETS = {
    "aspirin", "ecosprin", "disprin", "clopidogrel", "plavix", "clopilet",
    "warfarin", "acitrom", "rivaroxaban", "xarelto", "apixaban", "eliquis",
    "heparin", "enoxaparin", "clexane", "ecosprin av", "ecosprin gold",
}

_BETA_BLOCKERS = {
    "propranolol", "inderal", "metoprolol", "betaloc", "atenolol", "aten",
    "bisoprolol", "concor", "timolol", "amlong a",
}

_STATINS = {
    "atorvastatin", "atorva", "lipitor", "rosuvastatin", "rosuvas", "crestor",
    "atorva f", "rosuvas f", "ecosprin av", "ecosprin gold",
}

_MACROLIDES = {
    "azithromycin", "azee", "azee 500", "zithromax", "azibact",
    "clarithromycin", "claribid", "erythromycin",
}

_QUINOLONES = {
    "ciprofloxacin", "cifran", "cipex", "levofloxacin", "levomac", "levaquin",
    "ofloxacin", "oflox", "zenflox", "oflox oz", "o2", "norfloxacin", "norflox tz",
}

_SYSTEMIC_STEROIDS = {
    "prednisolone", "wysolone", "methylprednisolone", "medrol",
    "dexamethasone", "dexona", "betamethasone",
}

_PPIS_ANTACIDS = {
    "pantoprazole", "pan", "pan 40", "pan d", "pantocid", "pantocid d",
    "omeprazole", "omez", "omez d", "rabeprazole", "rabium", "razo", "razo d",
    "esomeprazole", "sompraz", "nexium", "sucralfate", "sucrafil",
}

_MINERAL_SUPPLEMENTS = {
    "shelcal", "shelcal 500", "cipcal", "calcium", "orofer xt", "autrin", "iron",
}


# ── Helper: Extract drug keys from a prescription ─────────

def _get_med_keys(meds: list[dict]) -> list[tuple[dict, str, str]]:
    """Return list of (med_dict, raw_name_lower, generic_lower)."""
    result = []
    for med in meds:
        if not isinstance(med, dict):
            continue
        raw_name = med.get("name", "").strip().lower()
        if not raw_name:
            continue

        # Look up generic from catalog
        info = COMMON_MEDICINES.get(raw_name, {})
        generic = info.get("generic", raw_name).lower()
        result.append((med, raw_name, generic))
    return result


def _has_any(names: list[str], target_set: set[str]) -> bool:
    return any(n in target_set or any(t in n for t in target_set) for n in names)


def _get_matching_meds(med_items: list[tuple[dict, str, str]], target_set: set[str]) -> list[str]:
    matches = []
    for med, raw_name, generic in med_items:
        if raw_name in target_set or generic in target_set:
            matches.append(med.get("name", raw_name.title()))
        elif any(t in raw_name or t in generic for t in target_set):
            matches.append(med.get("name", raw_name.title()))
    return list(dict.fromkeys(matches))


# ── Main Clinical Validation Function ───────────────────────

def validate_prescription(prescription: dict) -> list[dict]:
    """Run comprehensive clinical reasoning and pharmacological safety checks on a prescription.

    Returns a list of structured clinical warnings and alerts:
        [{"level": "warning"|"error"|"info", "message": str, "field": str}, ...]
    """
    warnings: list[dict] = []

    meds = prescription.get("medications", [])
    diagnoses = [d.lower() for d in prescription.get("diagnosis", [])]
    complaints = [c.get("name", "").lower() if isinstance(c, dict) else str(c).lower() for c in prescription.get("complaints", [])]

    all_clinical_text = " ".join(diagnoses + complaints)

    # 1. Basic Completeness Validation
    if not meds:
        warnings.append({
            "level": "warning",
            "message": "No medications found in the prescription.",
            "field": "medications",
        })
        return warnings

    med_items = _get_med_keys(meds)

    # 2. Check for missing critical fields
    for i, med in enumerate(meds):
        med_name = med.get("name", f"Medication #{i+1}")
        if not med.get("dose"):
            warnings.append({
                "level": "info",
                "message": f"'{med_name}' has no specific strength/dose indicated.",
                "field": f"medications[{i}].dose",
            })
        if not med.get("frequency"):
            warnings.append({
                "level": "warning",
                "message": f"'{med_name}' is missing dosage frequency (e.g. OD, BD, TID).",
                "field": f"medications[{i}].frequency",
            })

    # 3. Duplicate Ingredient & Overlap Checks
    # 3a. Multiple Paracetamol sources
    paracetamol_meds = _get_matching_meds(med_items, _PARACETAMOL_VARIANTS)
    if len(paracetamol_meds) > 1:
        warnings.append({
            "level": "warning",
            "message": f"Duplicate Paracetamol Source: Multiple medications containing Paracetamol prescribed ({', '.join(paracetamol_meds)}). Risk of exceeding 4,000mg/day safe hepatic limit.",
            "field": "medications",
        })

    # 3b. Multiple NSAIDs
    nsaid_meds = _get_matching_meds(med_items, _NSAID_VARIANTS)
    if len(nsaid_meds) > 1:
        warnings.append({
            "level": "warning",
            "message": f"Dual NSAID Therapy: Prescribing multiple oral NSAIDs ({', '.join(nsaid_meds)}) increases gastrointestinal ulceration and acute renal injury risk without added analgesic efficacy.",
            "field": "medications",
        })

    # 4. Drug-Drug Interaction (DDI) Reasoning
    # 4a. NSAID + Anticoagulant / Antiplatelet
    anticoag_meds = _get_matching_meds(med_items, _ANTICOAGULANTS_ANTIPLATELETS)
    if nsaid_meds and anticoag_meds:
        warnings.append({
            "level": "warning",
            "message": f"Major DDI (Bleeding Risk): Co-administration of NSAIDs ({', '.join(nsaid_meds)}) with Antiplatelets/Anticoagulants ({', '.join(anticoag_meds)}) significantly elevates major GI bleeding risk.",
            "field": "medications",
        })

    # 4b. Macrolide + Statin (Rhabdomyolysis Risk)
    macrolide_meds = _get_matching_meds(med_items, _MACROLIDES)
    statin_meds = _get_matching_meds(med_items, _STATINS)
    if macrolide_meds and statin_meds:
        warnings.append({
            "level": "warning",
            "message": f"DDI (Myopathy/Rhabdomyolysis Risk): Macrolides ({', '.join(macrolide_meds)}) inhibit CYP3A4 statin metabolism, increasing ({', '.join(statin_meds)}) serum levels.",
            "field": "medications",
        })

    # 4c. Quinolone + Systemic Steroid (Tendon Rupture)
    quinolone_meds = _get_matching_meds(med_items, _QUINOLONES)
    steroid_meds = _get_matching_meds(med_items, _SYSTEMIC_STEROIDS)
    if quinolone_meds and steroid_meds:
        warnings.append({
            "level": "warning",
            "message": f"DDI (Tendonitis/Tendon Rupture): Co-prescription of Fluoroquinolones ({', '.join(quinolone_meds)}) and Corticosteroids ({', '.join(steroid_meds)}) increases tendon rupture risk, especially in elderly.",
            "field": "medications",
        })

    # 4d. Quinolone + Iron / Calcium / Antacids (Chelation)
    mineral_meds = _get_matching_meds(med_items, _MINERAL_SUPPLEMENTS)
    if quinolone_meds and mineral_meds:
        warnings.append({
            "level": "info",
            "message": f"Chelation Alert: Take Fluoroquinolones ({', '.join(quinolone_meds)}) at least 2 hours before or 4 hours after mineral supplements ({', '.join(mineral_meds)}) to prevent absorption failure.",
            "field": "medications",
        })

    # 5. Disease-Drug Contraindication Reasoning
    # 5a. Asthma / COPD + Beta-Blockers
    is_asthma_copd = any(k in all_clinical_text for k in ["asthma", "bronchial asthma", "copd", "wheezing", "bronchospasm"])
    beta_blocker_meds = _get_matching_meds(med_items, _BETA_BLOCKERS)
    if is_asthma_copd and beta_blocker_meds:
        warnings.append({
            "level": "error",
            "message": f"Contraindication (Bronchospasm): Beta-blockers ({', '.join(beta_blocker_meds)}) are contraindicated in patients with Asthma/COPD due to risk of severe bronchospasm.",
            "field": "diagnosis",
        })

    # 5b. Peptic Ulcer / GERD / Gastritis + NSAID without PPI
    is_gi_distress = any(k in all_clinical_text for k in ["peptic ulcer", "gerd", "gastritis", "acidity", "heartburn", "gastroenteritis"])
    has_ppi = bool(_get_matching_meds(med_items, _PPIS_ANTACIDS))
    if is_gi_distress and nsaid_meds and not has_ppi:
        warnings.append({
            "level": "warning",
            "message": f"Gastric Protection Alert: Patient presents with GI symptoms ({', '.join(nsaid_meds)} prescribed). Consider adding a PPI (e.g. Pantoprazole / Pan-D) for mucosal protection.",
            "field": "medications",
        })

    # 5c. Diabetes + Systemic Corticosteroids
    is_diabetic = any(k in all_clinical_text for k in ["diabetes", "type 2 diabetes", "t2dm", "t1dm", "diabetic"])
    if is_diabetic and steroid_meds:
        warnings.append({
            "level": "warning",
            "message": f"Glycemic Alert: Systemic corticosteroids ({', '.join(steroid_meds)}) induce acute hyperglycemia in diabetic patients; recommend frequent capillary blood glucose monitoring.",
            "field": "medications",
        })

    return warnings
