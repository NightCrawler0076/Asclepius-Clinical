"""
Clinical Transcript Cleaner.

Normalizes raw Whisper output before clinical entity extraction.
Whisper reliably transcribes speech but produces:
  - Spoken numbers: "five hundred" instead of "500"
  - Spoken abbreviations: "b d" / "b.d." instead of "BD"
  - Split brand names: "augment in" instead of "Augmentin"
  - Long-form units: "milligrams" instead of "mg"

This module applies lightweight regex transformations to fix the most
common ASR artifacts that hurt downstream extraction accuracy.
All transforms are idempotent and safe to apply multiple times.
"""

import re


# ── 1. Spoken Number → Digit Normalization ─────────────────────────────────
# Ordered compound-first to avoid partial replacements.
# Covers numbers doctors typically dictate for doses and durations.

_NUMBER_MAP: list[tuple[re.Pattern, str]] = [
    # Common dose composites spoken as phrases (check before singles)
    (re.compile(r"\b6\s*fifty\b",             re.I), "650"),
    (re.compile(r"\b5\s*hundred\b",           re.I), "500"),
    (re.compile(r"\b2\s*fifty\b",             re.I), "250"),
    (re.compile(r"\b1\s*twenty\s*5\b",        re.I), "125"),
    (re.compile(r"\b8\s*seventy\s*5\b",       re.I), "875"),
    # Word numbers (compound before singles)
    (re.compile(r"\bthirty\b",    re.I), "30"),
    (re.compile(r"\btwenty\b",    re.I), "20"),
    (re.compile(r"\bfourteen\b",  re.I), "14"),
    (re.compile(r"\bthirteen\b",  re.I), "13"),
    (re.compile(r"\btwelve\b",    re.I), "12"),
    (re.compile(r"\beleven\b",    re.I), "11"),
    (re.compile(r"\bten\b",       re.I), "10"),
    (re.compile(r"\bnine\b",      re.I), "9"),
    (re.compile(r"\beight\b",     re.I), "8"),
    (re.compile(r"\bseven\b",     re.I), "7"),
    (re.compile(r"\bsix\b",       re.I), "6"),
    (re.compile(r"\bfive\b",      re.I), "5"),
    (re.compile(r"\bfour\b",      re.I), "4"),
    (re.compile(r"\bthree\b",     re.I), "3"),
    (re.compile(r"\btwo\b",       re.I), "2"),
    (re.compile(r"\bone\b",       re.I), "1"),
    (re.compile(r"\bzero\b",      re.I), "0"),
    (re.compile(r"\ba half\b",    re.I), "0.5"),
    (re.compile(r"\bhalf\b",      re.I), "0.5"),
]


def _normalize_numbers(text: str) -> str:
    for pattern, replacement in _NUMBER_MAP:
        text = pattern.sub(replacement, text)
    return text


# ── 2. Frequency Abbreviation Normalization ─────────────────────────────────
# Spoken letter-by-letter abbreviations and misformed variants.

_FREQ_NORM: list[tuple[re.Pattern, str]] = [
    # Spaced / dotted letter-by-letter abbreviations (longer first)
    (re.compile(r"\bq\.?\s*i\.?\s*d\.?\b",    re.I), "QID"),
    (re.compile(r"\bt\.?\s*i\.?\s*d\.?\b",    re.I), "TID"),
    (re.compile(r"\bt\.?\s*d\.?\s*s\.?\b",    re.I), "TDS"),
    (re.compile(r"\bs\.?\s*o\.?\s*s\.?\b",    re.I), "SOS"),
    (re.compile(r"\bp\.?\s*r\.?\s*n\.?\b",    re.I), "PRN"),
    (re.compile(r"\bs\.?\s*t\.?\s*a\.?\s*t\.?\b", re.I), "STAT"),
    (re.compile(r"\bb\.?\s*d\.?\b",           re.I), "BD"),
    (re.compile(r"\bo\.?\s*d\.?\b",           re.I), "OD"),
    # Spoken phrase equivalents
    (re.compile(r"\bfour\s+times\s+(?:a\s+)?day\b",  re.I), "QID"),
    (re.compile(r"\bthrice\s+(?:a\s+)?day\b",        re.I), "TID"),
    (re.compile(r"\bthree\s+times\s+(?:a\s+)?day\b", re.I), "TID"),
    (re.compile(r"\btwice\s+(?:a\s+)?day\b",         re.I), "BD"),
    (re.compile(r"\btwice\s+daily\b",                re.I), "BD"),
    (re.compile(r"\bonce\s+(?:a\s+)?day\b",          re.I), "OD"),
    (re.compile(r"\bonce\s+daily\b",                 re.I), "OD"),
    (re.compile(r"\bas\s+and\s+when\s+required\b",   re.I), "SOS"),
    (re.compile(r"\bif\s+(?:needed|required|pain|fever)\b", re.I), "SOS"),
    (re.compile(r"\bimmediately\b",                  re.I), "STAT"),
    (re.compile(r"\burgently\b",                     re.I), "STAT"),
]


def _normalize_frequencies(text: str) -> str:
    for pattern, replacement in _FREQ_NORM:
        text = pattern.sub(replacement, text)
    return text


# ── 3. Unit Longform → Abbreviation ────────────────────────────────────────

_UNIT_NORM: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bmilligrams?\b",           re.I), "mg"),
    (re.compile(r"\bmicrograms?\b",           re.I), "mcg"),
    (re.compile(r"\bnanograms?\b",            re.I), "ng"),
    (re.compile(r"\bgrams?\b",                re.I), "g"),
    (re.compile(r"\bmillilitres?\b",          re.I), "ml"),
    (re.compile(r"\bmilliliters?\b",          re.I), "ml"),
    (re.compile(r"\binternational\s+units?\b", re.I), "IU"),
    (re.compile(r"\bpercent\b",               re.I), "%"),
    (re.compile(r"\bcc\b",                    re.I), "ml"),
]


def _normalize_units(text: str) -> str:
    for pattern, replacement in _UNIT_NORM:
        text = pattern.sub(replacement, text)
    return text


# ── 4. Common ASR Split-Word / Mishearing Corrections ──────────────────────
# Specific known Whisper errors for common Indian brand names and
# investigation abbreviations spoken letter-by-letter.

_ASR_CORRECTIONS: list[tuple[re.Pattern, str]] = [
    # Antibiotic split-words
    (re.compile(r"\baugment\s+in\b",          re.I), "Augmentin"),
    (re.compile(r"\baugment\s+tin\b",         re.I), "Augmentin"),
    (re.compile(r"\bamoxi\s*clav\b",          re.I), "Amoxiclav"),
    (re.compile(r"\bazithro\s+mycin\b",       re.I), "Azithromycin"),
    (re.compile(r"\bcipro\s+floxacin\b",      re.I), "Ciprofloxacin"),
    (re.compile(r"\bmetronida\s+zole\b",      re.I), "Metronidazole"),
    (re.compile(r"\bcefix\s*ime\b",           re.I), "Cefixime"),
    (re.compile(r"\bdoxycycl\s+ine\b",        re.I), "Doxycycline"),
    (re.compile(r"\bnitrofurant\s+oin\b",     re.I), "Nitrofurantoin"),
    (re.compile(r"\boflo\s+xacin\b",          re.I), "Ofloxacin"),
    # Analgesic / GI split-words
    (re.compile(r"\bpara\s*cetamol\b",        re.I), "Paracetamol"),
    (re.compile(r"\bibupro\s+fen\b",          re.I), "Ibuprofen"),
    (re.compile(r"\bdiclo\s+fenac\b",         re.I), "Diclofenac"),
    (re.compile(r"\bpanto\s+prazole\b",       re.I), "Pantoprazole"),
    (re.compile(r"\bomepra\s+zole\b",         re.I), "Omeprazole"),
    (re.compile(r"\bondanse\s+tron\b",        re.I), "Ondansetron"),
    (re.compile(r"\bdomperi\s+done\b",        re.I), "Domperidone"),
    (re.compile(r"\brabepr\s+azole\b",        re.I), "Rabeprazole"),
    # Cardiac / metabolic split-words
    (re.compile(r"\bamlodi\s+pine\b",         re.I), "Amlodipine"),
    (re.compile(r"\btelmisar\s+tan\b",        re.I), "Telmisartan"),
    (re.compile(r"\batorvasta\s+tin\b",       re.I), "Atorvastatin"),
    (re.compile(r"\brosuvasta\s+tin\b",       re.I), "Rosuvastatin"),
    (re.compile(r"\bmetfor\s+min\b",          re.I), "Metformin"),
    (re.compile(r"\bglimepir\s+ide\b",        re.I), "Glimepiride"),
    (re.compile(r"\blevothyrox\s+ine\b",      re.I), "Levothyroxine"),
    (re.compile(r"\bcetiri\s+zine\b",         re.I), "Cetirizine"),
    (re.compile(r"\blevocetiri\s+zine\b",     re.I), "Levocetirizine"),
    (re.compile(r"\bmonteluk\s+ast\b",        re.I), "Montelukast"),
    (re.compile(r"\bsalbuta\s+mol\b",         re.I), "Salbutamol"),
    # Common brand name / dose spoken forms
    (re.compile(r"\bdolo\s+(?:six\s+fifty|650)\b", re.I), "Dolo 650"),
    (re.compile(r"\bpan\s+d\b",                    re.I), "Pan-D"),
    (re.compile(r"\bglyco\s+met\b",                re.I), "Glycomet"),
    # Investigation abbreviations spoken as spaced letters
    (re.compile(r"\bh\s*b\s*a\s*1\s*c\b",  re.I), "HbA1c"),
    (re.compile(r"\bt\s*s\s*h\b",          re.I), "TSH"),
    (re.compile(r"\bl\s*f\s*t\b",          re.I), "LFT"),
    (re.compile(r"\bk\s*f\s*t\b",          re.I), "KFT"),
    (re.compile(r"\be\s*c\s*g\b",          re.I), "ECG"),
    (re.compile(r"\bc\s*b\s*c\b",          re.I), "CBC"),
    (re.compile(r"\br\s*b\s*s\b",          re.I), "RBS"),
    (re.compile(r"\bf\s*b\s*s\b",          re.I), "FBS"),
    (re.compile(r"\bu\s*s\s*g\b",          re.I), "USG"),
    (re.compile(r"\bh\s*r\s*c\s*t\b",     re.I), "HRCT"),
    (re.compile(r"\bp\s*f\s*t\b",          re.I), "PFT"),
]


def _apply_asr_corrections(text: str) -> str:
    for pattern, replacement in _ASR_CORRECTIONS:
        text = pattern.sub(replacement, text)
    return text


# ── 5. Punctuation Injection ────────────────────────────────────────────────
# Adds a comma after duration patterns when followed by a capitalized drug name
# to help extractor.py's clause-isolation logic separate medication entries.
# e.g. "Augmentin 625mg BD for 5 days Dolo 650mg TID" →
#      "Augmentin 625mg BD for 5 days, Dolo 650mg TID"

_MED_BOUNDARY = re.compile(
    r"((?:for\s+)?\d+\s*(?:days?|weeks?|months?))"  # duration phrase
    r"(\s+)"                                          # whitespace
    r"(?=[A-Z][a-z]{2,})",                           # next capitalized word (drug name)
)


def _inject_punctuation(text: str) -> str:
    """Add commas at medication boundaries to improve clause isolation."""
    return _MED_BOUNDARY.sub(r"\1,\2", text)


# ── Public API ──────────────────────────────────────────────────────────────

def clean(transcript: str) -> str:
    """Apply the full normalization pipeline to a raw Whisper transcript.

    Transform order matters:
      1. Numbers first  → so "five milligrams" becomes "5 milligrams"
      2. Units second   → so "5 milligrams" becomes "5 mg"
      3. Frequencies    → so "twice a day" becomes "BD"
      4. ASR corrections→ fix split brand names after prior steps are clean
      5. Punctuation    → inject commas at medication boundaries

    Returns the cleaned transcript string.
    """
    if not transcript or not transcript.strip():
        return transcript

    text = transcript

    text = _normalize_numbers(text)
    text = _normalize_units(text)
    text = _normalize_frequencies(text)
    text = _apply_asr_corrections(text)
    text = _inject_punctuation(text)

    # Collapse multiple spaces introduced by substitutions
    text = re.sub(r"  +", " ", text)

    return text.strip()
