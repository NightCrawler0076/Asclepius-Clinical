"""
Clinical entity extractor.

Uses comprehensive medical dictionaries, phonetic algorithms, and structured
frequency/duration normalization to extract clinical information from spoken transcripts.
"""

import re
from clinical.medicines import COMMON_MEDICINES, NON_MEDICINAL_WORDS
from clinical.normalizer import fuzzy_match_drug, is_valid_medicine_token


def extract(text: str) -> dict:
    """Extract clinical entities from transcript text.

    Returns a dict matching the prescription schema fields:
        complaints, diagnosis, medications, investigations, advice,
        follow_up, doctor_notes.
    """
    text_lower = text.lower()

    return {
        "complaints": _extract_complaints(text_lower),
        "diagnosis": _extract_diagnosis(text_lower),
        "medications": _extract_medications(text),
        "investigations": _extract_investigations(text_lower),
        "advice": _extract_advice(text_lower),
        "follow_up": _extract_follow_up(text_lower),
        "doctor_notes": "",
    }


# ── Complaints / Symptoms ─────────────────────────────────
# Ordered longest-first so multi-word phrases match before their sub-words.
_SYMPTOM_KEYWORDS = sorted([
    # Pain & aches
    "headache", "chest pain", "chest tightness", "abdominal pain", "abdominal cramps",
    "stomach pain", "stomach ache", "cramps", "spasms",
    "back pain", "joint pain", "knee pain", "hip pain", "shoulder pain",
    "neck pain", "leg pain", "muscle pain", "body ache", "body pain",
    "ear pain", "eye pain", "throat pain", "tooth pain", "toothache",
    "burning pain", "burning sensation", "burning urination", "dysuria",
    "jaw pain", "calf pain", "flank pain", "pelvic pain",
    # Respiratory
    "cough", "cold", "runny nose", "running nose", "blocked nose", "nasal congestion",
    "breathlessness", "shortness of breath", "difficulty breathing", "wheezing",
    "sore throat", "throat irritation", "sneezing",
    "blood in sputum", "hemoptysis",
    # GI
    "vomiting", "nausea", "diarrhea", "loose motions", "loose stools",
    "constipation", "acidity", "heartburn", "indigestion", "bloating",
    "gas", "flatulence", "loss of appetite", "anorexia",
    # General
    "fever", "fatigue", "weakness", "tiredness", "lethargy", "malaise",
    "weight loss", "weight gain", "swelling", "edema", "oedema",
    "rash", "itching", "itchiness", "bleeding", "blood in urine",
    "blood in stool", "dark urine", "chills", "rigors", "night sweats",
    "lump", "breast lump",
    # Neuro / Cardio
    "dizziness", "vertigo", "fainting", "syncope", "palpitations",
    "rapid heartbeat", "irregular heartbeat", "tremor", "numbness",
    "tingling", "seizure", "convulsion",
    "photophobia", "tinnitus", "neck stiffness",
    # Psych / Sleep
    "anxiety", "depression", "insomnia", "sleeplessness", "mood changes",
    # Urology / Gynaec
    "frequent urination", "polyuria", "difficulty urinating",
    "urinary retention", "foul smelling urine",
    "missed period", "irregular periods", "vaginal discharge",
    # Metabolic
    "excessive thirst", "polydipsia", "excessive hunger", "polyphagia",
    "dry mouth", "dry eyes",
    # ENT / Eyes
    "ear discharge", "hearing loss", "blurred vision", "double vision",
    "eye redness", "watering eyes",
    # Dermatology
    "skin peeling", "hair loss", "alopecia",
], key=len, reverse=True)


def _extract_complaints(text: str) -> list[dict]:
    """Find symptom keywords.

    Per clinical guidelines, does NOT attach duration of sickness to complaints
    in the formal prescription draft.
    """
    extracted_complaints = []
    seen_complaints: set[str] = set()

    for symptom in _SYMPTOM_KEYWORDS:
        symptom_regex = re.compile(rf"\b{re.escape(symptom)}\b", re.IGNORECASE)
        if symptom_regex.search(text) and symptom not in seen_complaints:
            seen_complaints.add(symptom)
            # Duration of sickness is intentionally omitted from the prescription output
            extracted_complaints.append({"name": symptom, "duration": ""})

    return extracted_complaints


# ── Diagnosis ──────────────────────────────────────────────

_DIAGNOSIS_MARKERS = [
    "provisional diagnosis", "final diagnosis", "diagnosis is", "diagnosed with",
    "impression is", "impression", "assessment", "a case of", "known case of",
    "case of", "appears to be", "looks like", "suffering from", "c/o",
]
_DIAGNOSIS_MARKERS_SORTED = sorted(_DIAGNOSIS_MARKERS, key=len, reverse=True)


# Common disease / condition names that should be captured even without an
# explicit "diagnosis is" / "diagnosed with" marker phrase.
# Ordered longest-first to prefer specific multi-word matches.
_DISEASE_KEYWORDS = sorted([
    # Infections
    "upper respiratory tract infection", "urinary tract infection",
    "acute respiratory infection", "lower respiratory tract infection",
    "urti", "lrti", "uti", "respiratory infection",
    "viral fever", "bacterial infection",
    "typhoid", "dengue fever", "dengue", "malaria", "chickenpox", "measles",
    "covid", "influenza", "gastroenteritis", "food poisoning",
    "throat infection", "ear infection", "otitis media",
    "pneumonia", "bronchitis", "bronchiolitis", "sinusitis", "pharyngitis",
    "tonsillitis", "conjunctivitis",
    "tuberculosis", "tb", "pulmonary tuberculosis",
    "cellulitis", "abscess", "herpes zoster", "shingles",
    "hepatitis a", "hepatitis b", "hepatitis c", "hepatitis",
    "hiv", "sepsis", "septicemia",
    "urinary sepsis", "wound infection",
    # Chronic
    "type 2 diabetes mellitus", "type 1 diabetes mellitus",
    "diabetes mellitus", "diabetes",
    "hypertension", "essential hypertension",
    "hypothyroidism", "hyperthyroidism", "thyroid disorder",
    "bronchial asthma", "asthma", "copd",
    "chronic kidney disease", "ckd", "renal failure",
    "gerd", "gastroesophageal reflux", "peptic ulcer", "ibs",
    "anemia", "anaemia", "iron deficiency anemia",
    "vitamin d deficiency", "vitamin b12 deficiency",
    # Endocrine
    "cushing syndrome", "addison disease",
    "pcos", "polycystic ovary syndrome", "polycystic ovarian disease",
    # Cardiac
    "coronary artery disease", "cad", "heart failure", "cardiac failure",
    "atrial fibrillation", "myocardial infarction", "angina",
    "dyslipidemia", "hyperlipidemia", "hypercholesterolemia",
    "deep vein thrombosis", "dvt", "pulmonary embolism",
    "pericarditis", "endocarditis", "cardiomyopathy",
    # Musculoskeletal
    "rheumatoid arthritis", "osteoarthritis", "arthritis",
    "osteoporosis", "gout", "fibromyalgia", "back pain", "sciatica",
    "cervical spondylosis", "lumbar spondylosis", "spondylitis",
    "disc prolapse", "disc herniation", "slipped disc",
    "frozen shoulder", "carpal tunnel syndrome", "plantar fasciitis",
    "tennis elbow", "lateral epicondylitis",
    # Neuro / Psych
    "migraine", "tension headache", "epilepsy", "seizure disorder",
    "anxiety disorder", "depression", "insomnia",
    "stroke", "cerebrovascular accident", "cva",
    "parkinson disease", "parkinsonism",
    "bell palsy", "trigeminal neuralgia", "neuropathy",
    "diabetic neuropathy", "peripheral neuropathy",
    # Renal
    "nephrotic syndrome", "nephrolithiasis", "kidney stone", "renal calculus",
    "renal colic", "hydronephrosis",
    # Hepato / GI
    "fatty liver", "nafld", "non-alcoholic fatty liver disease",
    "cirrhosis", "jaundice", "hepatic encephalopathy",
    "crohn disease", "ulcerative colitis", "ibd", "inflammatory bowel disease",
    "pancreatitis", "acute pancreatitis", "chronic pancreatitis",
    "cholelithiasis", "gallstones", "cholecystitis",
    # Respiratory
    "pleural effusion", "lung abscess", "interstitial lung disease",
    "pulmonary fibrosis", "pulmonary hypertension",
    # Skin / Allergy
    "allergic rhinitis", "urticaria", "eczema", "dermatitis", "psoriasis",
    "fungal infection", "scabies",
    "acne vulgaris", "contact dermatitis", "seborrheic dermatitis",
    # Pediatric
    "hand foot mouth disease", "croup", "febrile seizure",
    # Other
    "dehydration", "malnutrition",
    "benign prostatic hyperplasia", "bph",
    "erectile dysfunction",
    "varicose veins", "hemorrhoids", "piles",
], key=len, reverse=True)


def _extract_diagnosis(text: str) -> list[str]:
    """Look for diagnosis markers and grab the following phrase.
    Falls back to direct disease keyword matching when no marker is present.
    """
    extracted_diagnoses = []
    seen_diagnoses: set[str] = set()

    for marker in _DIAGNOSIS_MARKERS_SORTED:
        marker_index = text.find(marker)
        if marker_index != -1:
            # Extended window: 120 chars; split on sentence-end or semicolon/newline first
            following_text = text[marker_index + len(marker): marker_index + len(marker) + 120]
            # Split on hard stops and newlines/semicolons before splitting on commas
            hard_stop = re.split(r"[.!?\n;]", following_text)[0]
            # A comma may separate co-morbidities joined by "with" — keep those together
            # e.g. "Type 2 DM with Hypertension, Dyslipidemia" → two entries split at comma
            sub_phrases = re.split(r",\s*(?!\s*(?:with|and)\s+[a-z])", hard_stop)
            for phrase in sub_phrases:
                clean_phrase = phrase.strip()
                phrase_key = clean_phrase.lower()
                if clean_phrase and phrase_key not in seen_diagnoses and len(clean_phrase) > 2:
                    seen_diagnoses.add(phrase_key)
                    extracted_diagnoses.append(clean_phrase)

    # Fallback: direct disease keyword scan (catches "patient has URTI", "known case of asthma")
    for disease in _DISEASE_KEYWORDS:
        if re.search(rf"\b{re.escape(disease)}\b", text, re.IGNORECASE):
            disease_key = disease.lower()
            if disease_key not in seen_diagnoses:
                # Check it isn't already covered as a substring of an existing entry
                already_covered = any(disease_key in existing.lower() for existing in extracted_diagnoses)
                if not already_covered:
                    seen_diagnoses.add(disease_key)
                    extracted_diagnoses.append(disease.title())

    return extracted_diagnoses


# ── Structured Frequency Normalizer ───────────────────────

_FREQ_MAP: list[tuple[re.Pattern, str]] = [
    # Numeric Indian Dosing (e.g. 1-1-1-1, 1-0-1)
    (re.compile(r"\b1\s*-\s*1\s*-\s*1\s*-\s*1\b"), "QID (4 times a day)"),
    (re.compile(r"\b1\s*-\s*1\s*-\s*1\b"), "TID (Three times a day)"),
    (re.compile(r"\b1\s*-\s*0\s*-\s*1\b"), "BD (Twice a day)"),
    (re.compile(r"\b1\s*-\s*1\s*-\s*0\b"), "BD (Morning and Afternoon)"),
    (re.compile(r"\b0\s*-\s*1\s*-\s*1\b"), "BD (Afternoon and Night)"),
    (re.compile(r"\b1\s*-\s*0\s*-\s*0\b"), "OD (Morning)"),
    (re.compile(r"\b0\s*-\s*0\s*-\s*1\b"), "OD (Night)"),
    (re.compile(r"\b0\s*-\s*1\s*-\s*0\b"), "OD (Afternoon)"),

    # Spoken number patterns
    (re.compile(r"\b(?:one|1)\s+(?:one|1)\s+(?:one|1)\b", re.I), "TID (Three times a day)"),
    (re.compile(r"\b(?:one|1)\s+(?:zero|0)\s+(?:one|1)\b", re.I), "BD (Twice a day)"),
    (re.compile(r"\b(?:one|1)\s+(?:zero|0)\s+(?:zero|0)\b", re.I), "OD (Morning)"),
    (re.compile(r"\b(?:zero|0)\s+(?:zero|0)\s+(?:one|1)\b", re.I), "OD (Night)"),

    # Spoken times per day
    (re.compile(r"\b(?:four\s+times|4\s+times|4x|four\s+doses?|4\s+doses?)\s*(?:a\s+|per\s+|every\s+)?(?:day|daily)\b", re.I), "QID (4 times a day)"),
    (re.compile(r"\b(?:thrice|three\s+times|3\s+times|3x|three\s+doses?|3\s+doses?)\s*(?:a\s+|per\s+|every\s+)?(?:day|daily)\b", re.I), "TID (Three times a day)"),
    (re.compile(r"\b(?:twice|two\s+times|2\s+times|2x|two\s+doses?|2\s+doses?)\s*(?:a\s+|per\s+|every\s+)?(?:day|daily)\b", re.I), "BD (Twice a day)"),
    (re.compile(r"\b(?:once|one\s+time|1\s+time|1x|single\s+dose)\s*(?:a\s+|per\s+|every\s+)?(?:day|daily)\b", re.I), "OD (Once a day)"),
    (re.compile(r"\b(?:daily|every\s+day)\b", re.I), "OD (Once a day)"),

    # Spoken Day-Parts
    (re.compile(r"\b(?:morning[\s,]+(?:afternoon|noon)[\s,]+(?:and\s+)?(?:evening|night))\b", re.I), "TID (Morning, Afternoon, Night)"),
    (re.compile(r"\b(?:morning[\s,]+(?:and\s+)?(?:evening|night|bed\s*time))\b", re.I), "BD (Morning and Night)"),
    (re.compile(r"\b(?:breakfast[\s,]+(?:and\s+)?(?:dinner|night))\b", re.I), "BD (With Breakfast & Dinner)"),
    (re.compile(r"\b(?:at\s+bed\s*time|before\s+bed|at\s+night|in\s+the\s+night|every\s+night|night\s+only)\b", re.I), "OD (At Bedtime)"),
    (re.compile(r"\b(?:in\s+the\s+morning|every\s+morning|morning\s+only|with\s+breakfast|morning\s+empty\s+stomach)\b", re.I), "OD (Morning)"),
    (re.compile(r"\b(?:in\s+the\s+afternoon|afternoon\s+only|with\s+lunch)\b", re.I), "OD (Afternoon)"),

    # Hourly intervals
    (re.compile(r"\b(?:every\s+4\s*hours?|4\s*hourly|q4h)\b", re.I), "Every 4 hours"),
    (re.compile(r"\b(?:every\s+6\s*hours?|6\s*hourly|q6h)\b", re.I), "Every 6 hours"),
    (re.compile(r"\b(?:every\s+8\s*hours?|8\s*hourly|q8h)\b", re.I), "Every 8 hours"),
    (re.compile(r"\b(?:every\s+12\s*hours?|12\s*hourly|q12h)\b", re.I), "Every 12 hours"),

    # Periodic / Weekly / Monthly
    (re.compile(r"\b(?:alternate\s+days?|every\s+other\s+day)\b", re.I), "Alternate Days"),
    (re.compile(r"\b(?:once\s+(?:a\s+)?week|once\s+weekly|weekly\s+once)\b", re.I), "Once a week"),
    (re.compile(r"\b(?:twice\s+(?:a\s+)?week|twice\s+weekly)\b", re.I), "Twice a week"),
    (re.compile(r"\b(?:once\s+(?:a\s+)?month|monthly)\b", re.I), "Once a month"),

    # SOS / As needed
    (re.compile(r"\b(?:if\s+needed|whenever\s+needed|when\s+needed|as\s+needed|as\s+and\s+when\s+required|when\s+required|if\s+required|as\s+necessary|on\s+demand|if\s+pain|when\s+pain|if\s+fever|when\s+fever)\b", re.I), "SOS (As Needed)"),

    # Standard Latin Abbreviations
    (re.compile(r"\b(?:bid|bd)\b", re.I), "BD (Twice a day)"),
    (re.compile(r"\b(?:tid|tds)\b", re.I), "TID (Three times a day)"),
    (re.compile(r"\b(?:qid|qds)\b", re.I), "QID (4 times a day)"),
    (re.compile(r"\b(?:od)\b", re.I), "OD (Once a day)"),
    (re.compile(r"\b(?:hs)\b", re.I), "OD (At Bedtime)"),
    (re.compile(r"\b(?:sos|prn)\b", re.I), "SOS (As Needed)"),
    (re.compile(r"\b(?:stat)\b", re.I), "STAT (Immediately)"),
]


def _normalize_frequency(text: str) -> str:
    """Return the normalized frequency string from text."""
    if not text:
        return ""
    for freq_pattern, canonical in _FREQ_MAP:
        if freq_pattern.search(text):
            return canonical
    return ""


# ── Structured Duration Normalizer ────────────────────────

_NUM_WORD_MAP = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "fourteen": "14", "twenty": "20", "thirty": "30", "a": "1",
}

_DURATION_PATTERN = re.compile(
    r"\b(?:(?:for|x|take\s+for|continue\s+for|course\s+of)\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|fourteen|twenty|thirty|a)\s*"
    r"(days?|weeks?|months?)\b",
    re.IGNORECASE,
)


def _normalize_duration(text: str) -> str:
    """Extract and normalize prescription treatment duration (e.g. '5 days', '2 weeks')."""
    m = _DURATION_PATTERN.search(text)
    if m:
        num_str = m.group(1).lower()
        unit = m.group(2).lower()
        # Normalize number word
        num = _NUM_WORD_MAP.get(num_str, num_str)
        # Pluralize unit properly
        if num == "1":
            unit = unit.rstrip("s")
        elif not unit.endswith("s"):
            unit = unit + "s"
        return f"{num} {unit}"
    return ""


# ── Route & Instructions ──────────────────────────────────

_ROUTE_MAP = [
    (re.compile(r"\b(?:intravenous(?:ly)?|i\.?v\.?)\b", re.I), "IV"),
    (re.compile(r"\b(?:intramuscular(?:ly)?|i\.?m\.?)\b", re.I), "IM"),
    (re.compile(r"\b(?:subcutaneous(?:ly)?|s\.?c\.?)\b", re.I), "SC"),
    (re.compile(r"\b(?:sublingual(?:ly)?|s\.?l\.?)\b", re.I), "SL"),
    (re.compile(r"\b(?:topical(?:ly)?|local(?:ly)?)\b", re.I), "Topical"),
    (re.compile(r"\b(?:inhal(?:e|ation)|nebulize(?:d)?)\b", re.I), "Inhaled"),
    (re.compile(r"\b(?:oral(?:ly)?|by\s+mouth|p\.?o\.?)\b", re.I), "Oral"),
]

def _extract_route(text: str) -> str:
    for route_pattern, route_label in _ROUTE_MAP:
        if route_pattern.search(text):
            return route_label
    return ""


_INSTRUCTION_PATTERN = re.compile(
    r"\b(after\s+(?:food|meals?|eating|breakfast|lunch|dinner)|"
    r"before\s+(?:food|meals?|eating|breakfast|lunch|dinner)|"
    r"with\s+(?:food|meals?|water|milk)|"
    r"on\s+empty\s+stomach|"
    r"at\s+bed\s*time|"
    r"with\s+warm\s+water|"
    r"sublingually?|"
    r"topically?|"
    r"inhal(?:e|ation)|"
    r"apply\s+(?:over|on|to))\b",
    re.IGNORECASE,
)

def _extract_instruction(text: str) -> str:
    m = _INSTRUCTION_PATTERN.search(text)
    return m.group(0).strip() if m else ""


# ── Medication Extraction Core ────────────────────────────

def _get_isolated_context(text: str, start: int, end: int) -> tuple[str, str]:
    """Extract the specific sentence and isolated clause for a medication match."""
    preceding_text = text[:start]
    trailing_text = text[end:]
    
    sentence_start_idx = 0
    previous_delimiters = list(re.finditer(r"[\.\n\?!;]+", preceding_text))
    if previous_delimiters:
        sentence_start_idx = previous_delimiters[-1].end()
    
    sentence_end_idx = len(text)
    next_delimiter = re.search(r"[\.\n\?!;]+", trailing_text)
    if next_delimiter:
        sentence_end_idx = end + next_delimiter.start()
        
    sentence = text[sentence_start_idx:sentence_end_idx].strip()
    relative_start = start - sentence_start_idx
    relative_end = end - sentence_start_idx
    
    clause_start_idx = 0
    for conjunction in re.finditer(r"\b(?:and(?:\s+also)?|also|plus|along\s+with|then)\b|,", sentence[:relative_start], re.I):
        clause_start_idx = conjunction.end()
        
    clause_end_idx = len(sentence)
    next_conjunction = re.search(r"\b(?:and(?:\s+also)?|also|plus|along\s+with|then)\b|,", sentence[relative_end:], re.I)
    if next_conjunction:
        clause_end_idx = relative_end + next_conjunction.start()
        
    clause = sentence[clause_start_idx:clause_end_idx].strip()
    context = clause if len(clause) > 15 else sentence
    after_text = sentence[relative_end:clause_end_idx].strip() or sentence[relative_end:].strip()
    return context, after_text


# Verb / dosage form prefixes
_MED_PREFIX_PATTERN = (
    r"(?:(?:take|give|prescribe|start|continue|advise|use)\s+)?"
    r"(?:\d+|one|two|three|four|five|half|a|an)?\s*"
    r"(?:tabs?|tablets?|caps?|capsules?|syrups?|injections?|inj|drops?|inhalers?|creams?|ointments?|gels?|lotions?|patches?|suppositor(?:y|ies)?|puffs?|vials?|ampoules?|spoons?|teaspoons?|bottles?|sachets?)\s+"
    r"(?:of\s+)?"
    r"|"
    r"(?:take|give|prescribe|start|continue|advise)\s+(?:a\s+|an\s+|the\s+)?"
)

_MED_REGEX = re.compile(
    rf"(?:{_MED_PREFIX_PATTERN})\s*"
    r"([a-zA-Z\-]+(?:\s+(?!\d+\s*(?:mg|ml|g|mcg|iu|units?|%|\b))[a-zA-Z\-]+)?)"
    r"(?:\s+(\d+\s*(?:mg|ml|g|mcg|iu|units?|%)))?",
    re.IGNORECASE,
)

_MED_DOSE_REGEX = re.compile(
    r"\b([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)"
    r"\s+(\d+\s*(?:mg|ml|g|mcg|iu|units?|%))",
)

_MED_NAME_PATTERN: re.Pattern | None = None


def _get_catalogue_regex() -> re.Pattern:
    global _MED_NAME_PATTERN
    if _MED_NAME_PATTERN is None:
        med_names = sorted(COMMON_MEDICINES.keys(), key=len, reverse=True)
        alternatives = "|".join(re.escape(name) for name in med_names)
        _MED_NAME_PATTERN = re.compile(
            rf"\b({alternatives})\b"
            r"(?:\s+(\d+\s*(?:mg|ml|g|mcg|iu|units?|%)))?",
            re.IGNORECASE,
        )
    return _MED_NAME_PATTERN


def _extract_medications(text: str) -> list[dict]:
    """Extract ONLY valid medications matching the pharmacology catalogue or verified medical patterns.
    Strictly filters out generic phrases (e.g. 'even if', 'rest', 'food', 'water').
    """
    extracted_medications: list[dict] = []
    seen_canonical: set[str] = set()

    def _process_candidate(raw_name: str, dosage: str, start: int, end: int) -> None:
        clean_name = raw_name.strip()
        # Clean leading/trailing noise
        clean_name = re.sub(r"^(?:take|give|start|prescribe|continue|advise|use|of|a|an|the|tab|tablet|cap|capsule)\s+", "", clean_name, flags=re.I).strip()
        clean_name = re.sub(r"\s+(?:od|bd|bid|tid|tds|qid|sos|stat|prn|daily|oral|iv|im|once|twice|thrice|morning|night|day|days|for|with|of)$", "", clean_name, flags=re.I).strip()

        token_lower = clean_name.lower()
        if not clean_name or len(clean_name) < 2 or token_lower in NON_MEDICINAL_WORDS:
            return

        # Validate with fuzzy/phonetic drug matcher
        match_result = fuzzy_match_drug(clean_name)
        if not match_result and not is_valid_medicine_token(clean_name):
            # NOT a medicine! Drop generic words like "even if"
            return

        canonical_name = match_result["normalized"] if match_result else clean_name.title()
        canonical_key = canonical_name.lower()

        if canonical_key in seen_canonical:
            return

        # Context isolation for Frequency & Duration
        clause_context, after_text = _get_isolated_context(text, start, end)

        # Check for negation/contraindication in the surrounding clause
        # (e.g., "avoid aspirin", "strictly do not take ibuprofen", "stop NSAIDs")
        negation_match = re.search(
            r"\b(?:avoid|strictly\s+avoid|do\s+not\s+(?:take|use|give)|dont\s+(?:take|use|give)|stop|contraindicated|allergic\s+to|no\s+need\s+of)\b",
            clause_context,
            re.IGNORECASE,
        )
        if negation_match and negation_match.start() < (start - (text.rfind('.', 0, start) + 1)):
            # This medication is in an avoidance/warning clause, not an active prescription
            return

        frequency = _normalize_frequency(clause_context)
        duration = _normalize_duration(after_text) or _normalize_duration(clause_context)
        route = _extract_route(clause_context)
        instructions = _extract_instruction(clause_context)

        seen_canonical.add(canonical_key)
        extracted_medications.append({
            "name": canonical_name,
            "dose": dosage.strip(),
            "route": route,
            "frequency": frequency,
            "duration": duration,
            "instructions": instructions,
        })

    # 1. Catalogue scan (highest confidence)
    cat_regex = _get_catalogue_regex()
    for m in cat_regex.finditer(text):
        _process_candidate(m.group(1), m.group(2) or "", m.start(), m.end())

    # 2. Dose anchored scan
    for m in _MED_DOSE_REGEX.finditer(text):
        _process_candidate(m.group(1), m.group(2) or "", m.start(), m.end())

    # 3. Prefixed candidate scan
    for m in _MED_REGEX.finditer(text):
        _process_candidate(m.group(1), m.group(2) or "", m.start(), m.end())

    return extracted_medications


# ── Investigations ─────────────────────────────────────────

_INVESTIGATION_KEYWORDS = sorted([
    "complete blood count", "cbc", "haemoglobin", "hemoglobin", "hb",
    "platelet count", "wbc count", "differential count", "esr", "peripheral smear",
    "blood sugar", "random blood sugar", "rbs", "fasting blood sugar", "fbs",
    "post prandial blood sugar", "ppbs", "hba1c", "blood glucose",
    "lipid profile", "cholesterol", "triglycerides", "ldl", "hdl",
    "liver function", "lft", "kidney function", "kft", "renal function",
    "creatinine", "urea", "uric acid", "electrolytes", "sodium", "potassium",
    "thyroid function", "thyroid", "tsh", "t3", "t4",
    "serum calcium", "vitamin d", "vitamin b12", "iron studies",
    "coagulation profile", "pt inr", "aptt",
    "urine test", "urine routine", "urine culture", "urine microscopy",
    "urine pregnancy test", "upt",
    "x-ray", "xray", "chest x-ray", "pa view", "chest pa",
    "ultrasound", "usg", "usg abdomen", "usg pelvis",
    "mri", "mri brain", "mri spine",
    "ct scan", "ct brain", "ct chest", "hrct",
    "2d echo", "echocardiography", "echo",
    "ecg", "ekg", "electrocardiogram",
    "tmt", "treadmill test", "holter",
    "blood culture", "sputum culture", "throat swab",
    "dengue", "malaria", "widal", "typhidot",
    "covid", "rapid antigen", "rt pcr",
    "pap smear", "mammography", "bone density", "dexa scan",
    "spirometry", "pft", "pulmonary function",
    "audiometry", "vision test",
], key=len, reverse=True)


def _extract_investigations(text: str) -> list[str]:
    extracted = []
    seen = set()
    for kw in _INVESTIGATION_KEYWORDS:
        if kw in text and kw not in seen:
            seen.add(kw)
            extracted.append(kw)
    return extracted


# ── Advice ─────────────────────────────────────────────────

_ADVICE_MARKERS = [
    "advice", "advise", "advised", "recommend", "instruct",
    "rest", "bed rest", "avoid exertion", "avoid exercise", "light activity",
    "avoid", "diet", "bland food", "light diet", "soft diet",
    "avoid spicy", "avoid oily", "avoid cold", "avoid alcohol",
    "drink plenty", "drink water", "oral hydration", "stay hydrated",
    "after food", "before food", "with meals", "empty stomach",
    "keep dry", "keep clean", "change dressing", "wound care",
    "quit smoking", "stop smoking", "reduce weight", "exercise regularly",
    "monitor", "check bp", "check sugar", "check temperature",
    "should", "must", "need to",
]


def _extract_advice(text: str) -> list[str]:
    extracted = []
    seen = set()
    sentences = re.split(r"[.!?]", text)
    for raw in sentences:
        s = raw.strip()
        s_lower = s.lower()
        if s_lower and s_lower not in seen and any(m in s_lower for m in _ADVICE_MARKERS):
            seen.add(s_lower)
            extracted.append(s)
    return extracted


# ── Follow-up ─────────────────────────────────────────────

_FOLLOWUP_PATTERN = re.compile(
    r"(?:follow[- ]?up|come\s+back|review|revisit|see\s+(?:me|you)\s+(?:again)?|"
    r"return|next\s+visit|next\s+appointment)\s*"
    r"(?:in|after|within)?\s*"
    r"((?:\d+\s*(?:days?|weeks?|months?))|"
    r"(?:one|two|three|four|five|six)\s*(?:days?|weeks?|months?)|"
    r"(?:a\s+)?week|"
    r"(?:a\s+)?month|"
    r"next\s+(?:week|month|monday|tuesday|wednesday|thursday|friday))?",
    re.IGNORECASE,
)


def _extract_follow_up(text: str) -> str:
    m = _FOLLOWUP_PATTERN.search(text)
    if m:
        period = (m.group(1) or "").strip()
        if period:
            return f"Follow up in {period}"
        return "Follow up advised"
    return ""
