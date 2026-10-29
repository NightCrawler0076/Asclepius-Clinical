"""
Phonetic & Fuzzy Speech Error Detection & Normalization Engine.

Combines:
1. Direct dictionary normalization
2. Medical Phonetic Encoder (handles English & Indian medical pronunciation variants)
3. Normalized Levenshtein edit-distance ratio fuzzy matching
4. Confidence scoring & candidate ranking
5. Strict non-medicinal word rejection
"""

import difflib
import re
from clinical.medicines import COMMON_MEDICINES, NON_MEDICINAL_WORDS, get_route_and_instructions


# ── Medical Phonetic Key Encoder ──────────────────────────

def phonetic_key(token: str) -> str:
    """Compute phonetic pronunciation signature for medical terms.
    Normalizes C/K/Q, PH/F, TH/T, Y/I, soft/hard G/J, and silent letters.
    """
    s = token.lower().strip()
    s = re.sub(r"[^a-z]", "", s)
    if not s:
        return ""

    # Homophone replacements
    s = re.sub(r"^kn", "n", s)
    s = re.sub(r"^ps", "s", s)
    s = re.sub(r"^pn", "n", s)
    s = re.sub(r"^wr", "r", s)
    s = re.sub(r"ph", "f", s)
    s = re.sub(r"gh", "f", s)
    s = re.sub(r"th", "t", s)
    s = re.sub(r"sh", "s", s)
    s = re.sub(r"ck", "k", s)
    s = re.sub(r"cc", "k", s)
    s = re.sub(r"ch", "k", s)
    s = re.sub(r"c([eiy])", r"s\1", s)
    s = re.sub(r"c", "k", s)
    s = re.sub(r"q", "k", s)
    s = re.sub(r"x", "ks", s)
    s = re.sub(r"z", "s", s)
    s = re.sub(r"w", "v", s)
    s = re.sub(r"g([eiy])", r"j\1", s)
    s = re.sub(r"y", "i", s)

    # Preserve first char, compress inner vowels
    first = s[0]
    rest = re.sub(r"[aeiou]", "", s[1:]) if len(s) > 1 else ""

    # Collapse repeated consonants
    res = first + re.sub(r"(.)\1+", r"\1", rest)
    return res[:8]


# ── American Soundex (with K/C initial normalization) ─────

def soundex(token: str) -> str:
    """Compute Soundex code with initial C/K and PH/F normalization."""
    token = re.sub(r"[^a-zA-Z]", "", token).upper()
    if not token:
        return ""

    # Initial sound normalization for medicine names
    if token.startswith("K") or token.startswith("Q"):
        token = "C" + token[1:]
    elif token.startswith("PH"):
        token = "F" + token[2:]

    first_char = token[0]
    mapping = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }

    encoded = []
    prev_code = mapping.get(first_char, "")

    for char in token[1:]:
        code = mapping.get(char, "0")
        if code != "0" and code != prev_code:
            encoded.append(code)
        prev_code = code

    res = first_char + "".join(encoded)
    return (res + "0000")[:4]


# ── Pre-computed Drug Phonetic Index ──────────────────────

_PHONETIC_INDEX = {}
for name, meta in COMMON_MEDICINES.items():
    _PHONETIC_INDEX[name] = {
        "name": name,
        "generic": meta["generic"],
        "category": meta["category"],
        "soundex": soundex(name),
        "phonetic": phonetic_key(name),
    }


# ── Common Medical Drug Suffixes & Patterns ───────────────
_DRUG_SUFFIXES = (
    "cillin", "mycin", "micin", "cycline", "oxacin", "nazole", "prazole",
    "sartan", "statin", "olol", "pril", "dipine", "glitin", "gliptin",
    "flozin", "tidine", "setron", "zepam", "zolam", "xetine", "pramine",
    "kof", "flam", "gesic", "spas", "cold", "plus", "forte", "mox",
    "cef", "ceph", "sulfa", "zole", "pine", "caine", "asone", "olone",
    "onide", "fenac", "profac", "profen", "dopa", "prost", "pressin",
)


def is_valid_medicine_token(token: str) -> bool:
    """Check if a token is a known medicinal name, alias, or valid drug construct."""
    token_clean = token.strip().lower()
    if not token_clean or len(token_clean) < 2:
        return False
    if token_clean in NON_MEDICINAL_WORDS:
        return False
    if token_clean in COMMON_MEDICINES:
        return True
    # Check suffixes
    if any(token_clean.endswith(sfx) for sfx in _DRUG_SUFFIXES if len(token_clean) >= len(sfx) + 3):
        return True
    return False


# ── Fuzzy Matching & Normalization ────────────────────────

def fuzzy_match_drug(token: str, threshold: float = 0.65) -> dict | None:
    """Fuzzy and phonetic match a token against the drug catalog.

    Rejects non-medicinal English words ('even if', 'rest', 'water', etc.).
    Returns candidate dict with:
        normalized: canonical generic name
        confidence: score between 0.0 and 1.0
        original: raw token input
        category: pharmacology category
    """
    token_clean = token.strip().lower()
    if not token_clean or len(token_clean) < 2:
        return None

    # Immediate rejection of generic English non-medicinal words
    if token_clean in NON_MEDICINAL_WORDS:
        return None

    # 1. Exact match in catalog
    if token_clean in COMMON_MEDICINES:
        info = COMMON_MEDICINES[token_clean]
        return {
            "original": token,
            "normalized": info["generic"],
            "matched_key": token_clean,
            "category": info["category"],
            "confidence": 1.0,
            "match_type": "exact",
            "needs_review": False,
        }

    token_soundex = soundex(token_clean)
    token_phon = phonetic_key(token_clean)

    best_match = None
    highest_score = 0.0

    for name, item in _PHONETIC_INDEX.items():
        # String Sequence Similarity (Levenshtein-style ratio)
        str_ratio = difflib.SequenceMatcher(None, token_clean, name).ratio()

        # Phonetic matching bonus
        soundex_match = (token_soundex == item["soundex"]) and bool(token_soundex)
        phonetic_match = (token_phon == item["phonetic"]) and bool(token_phon)

        combined_score = str_ratio
        if soundex_match and phonetic_match:
            combined_score = min(1.0, str_ratio + 0.22)
        elif soundex_match or phonetic_match:
            combined_score = min(1.0, str_ratio + 0.12)

        # Prefix matching for clinical abbreviations (e.g. amoxi -> amoxicillin, azithro -> azithromycin)
        if name.startswith(token_clean) and len(token_clean) >= 4:
            combined_score = max(combined_score, 0.88)

        if combined_score > highest_score:
            highest_score = combined_score
            best_match = {
                "original": token,
                "normalized": item["generic"],
                "matched_key": name,
                "category": item["category"],
                "confidence": round(combined_score, 2),
                "match_type": "phonetic_fuzzy",
                "needs_review": combined_score < 0.80,
            }

    # Only accept if matched with sufficient confidence
    if best_match and highest_score >= threshold:
        return best_match

    # If it ends with a recognized drug suffix, accept as novel drug with review
    if any(token_clean.endswith(sfx) for sfx in _DRUG_SUFFIXES if len(token_clean) >= len(sfx) + 3):
        return {
            "original": token,
            "normalized": token.strip().title(),
            "matched_key": None,
            "category": "Prescription Drug",
            "confidence": 0.70,
            "match_type": "suffix_match",
            "needs_review": False,
        }

    # Reject non-medicinal random words
    return None


def normalize_medication(name: str) -> dict:
    """Normalize a medication name using the phonetic & fuzzy matcher."""
    res = fuzzy_match_drug(name)
    if res:
        return res
    return {
        "original": name,
        "normalized": name.strip().title(),
        "confidence": 0.4,
        "needs_review": True,
    }


def normalize_entities(clinical_data: dict) -> dict:
    """Run normalization and phonetic error correction over all extracted entities.
    Filters out any non-medicinal items that failed validation.
    Auto-enriches route and instructions from drug catalog if missing.
    """
    if "medications" in clinical_data:
        valid_meds = []
        for med in clinical_data["medications"]:
            raw_name = med.get("name", "")
            result = fuzzy_match_drug(raw_name)
            if result:
                med["name"] = result["normalized"]
                med["_normalization"] = result
                if result.get("category") and result["category"] != "Unknown":
                    med["category"] = result["category"]

                # Auto-enrich route & instructions from catalog
                cat_info = get_route_and_instructions(raw_name)
                if not med.get("route") and cat_info.get("route"):
                    med["route"] = cat_info["route"]
                if not med.get("instructions") and cat_info.get("instructions"):
                    med["instructions"] = cat_info["instructions"]

                valid_meds.append(med)
            elif is_valid_medicine_token(raw_name):
                med["name"] = raw_name.strip().title()

                cat_info = get_route_and_instructions(raw_name)
                if not med.get("route") and cat_info.get("route"):
                    med["route"] = cat_info["route"]
                if not med.get("instructions") and cat_info.get("instructions"):
                    med["instructions"] = cat_info["instructions"]

                valid_meds.append(med)
            # If it's a generic word like "even if", it is completely dropped!

        clinical_data["medications"] = valid_meds

    return clinical_data
