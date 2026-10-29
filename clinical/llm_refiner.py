"""
LLM Refinement Engine for Clinical Entity Extraction.

Uses a small quantized language model (Qwen2.5-0.5B-Instruct Q4_K_M) as a
single-call post-processor to refine the regex/dictionary extraction.

Design principles:
- Minimal compute: single call per consultation, ~200-400 output tokens
- Edge-portable: runs on Raspberry Pi 5 (CPU-only, ~400 MB RAM)
- Graceful fallback: returns draft entities unchanged if model unavailable
- Dictionary-validated: LLM output is cross-checked against the drug catalog
"""

import json
import logging
import os
import re
import threading
import time

from config import (
    LLM_ENABLED, LLM_MODEL_DIR, LLM_MODEL_PATH, LLM_MODELS, DEFAULT_LLM_MODEL_KEY,
    LLM_N_GPU_LAYERS, LLM_N_THREADS, LLM_MAX_TOKENS, LLM_CONTEXT_SIZE, LLM_TEMPERATURE,
)
from clinical.normalizer import fuzzy_match_drug, is_valid_medicine_token
from clinical.medicines import NON_MEDICINAL_WORDS, get_route_and_instructions

logger = logging.getLogger(__name__)

# ── Model State ───────────────────────────────────────────

_llm_model = None
_loaded_model_key = None
_active_model_key = DEFAULT_LLM_MODEL_KEY
_llm_lock = threading.RLock()


def get_active_model_key() -> str:
    """Get the currently configured active model key."""
    return _active_model_key


def get_model_path(model_key: str | None = None) -> str:
    """Resolve absolute path to model GGUF file."""
    key = model_key or _active_model_key
    if key in LLM_MODELS:
        return os.path.join(LLM_MODEL_DIR, LLM_MODELS[key]["filename"])
    return LLM_MODEL_PATH


def list_available_models() -> list[dict]:
    """Return all registered models with their disk existence and active status."""
    result = []
    for key, info in LLM_MODELS.items():
        path = os.path.join(LLM_MODEL_DIR, info["filename"])
        exists = os.path.isfile(path)
        size_mb = round(os.path.getsize(path) / (1024 * 1024), 1) if exists else None
        result.append({
            "id": key,
            "name": info.get("name", key),
            "filename": info.get("filename", ""),
            "description": info.get("description", ""),
            "ram_mb": info.get("ram_mb", 0),
            "file_exists": exists,
            "file_size_mb": size_mb,
            "is_active": key == _active_model_key,
        })
    return result


def set_active_model(model_key: str) -> dict:
    """Switch active LLM model key. Unloads currently loaded model if changed."""
    global _active_model_key
    with _llm_lock:
        if model_key not in LLM_MODELS:
            raise ValueError(f"Unknown model key '{model_key}'. Available: {list(LLM_MODELS.keys())}")

        if model_key != _active_model_key:
            logger.info("Switching active LLM model from %s to %s", _active_model_key, model_key)
            unload_model()
            _active_model_key = model_key

        return get_status()


# ── System Prompt (optimized for ChatML / standard chat formats) ───

_SYSTEM_PROMPT = """You are an expert clinical pharmacologist and medical transcription extraction model.
Extract structured prescription entities from the doctor's consultation transcript.
Output ONLY a single valid JSON object matching this schema:
{
  "complaints": ["symptom name only"],
  "diagnosis": ["disease or clinical condition"],
  "medications": [
    {
      "name": "BrandName or GenericName",
      "dose": "standardized dosage (e.g. 500mg, 650mg, 10ml, 2 puffs)",
      "frequency": "OD / BD / TID / QID / SOS / STAT",
      "duration": "e.g. 5 days, 1 month, or empty",
      "route": "Oral / Inhaled / Topical / Nasal / Ophthalmic / Otic / IV / IM / SC",
      "instructions": "e.g. Take after food, before breakfast, at bedtime"
    }
  ],
  "investigations": ["lab tests, radiology, imaging"],
  "advice": ["dietary or lifestyle advice"],
  "follow_up": "follow-up time or review instruction"
}

Critical Clinical Rules:
1. PRESERVE SPOKEN MEDICINE NAMES:
   - Output the exact brand name or generic spoken by the physician (e.g. Dolo, Augmentin, Pan-40, Zerodol-SP, Shelcal, Montair-LC, Asthalin, Telma, Glycomet, Sorbitrate, Foracort, Urimax-D, AKT-4, Zentel, Permethrin, Moxicip, etc.).
   - Do NOT replace a specific prescribed brand with an alternate generic unless the brand is an informal abbreviation.
2. STRICT NEGATIVE MEDICATION / CONTRAINDICATION FILTER:
   - DO NOT include medications that the doctor explicitly says to AVOID, STOP, or NOT TAKE.
   - Example: "Avoid aspirin and ibuprofen", "Stop NSAIDs" -> DO NOT extract aspirin or ibuprofen as prescribed medications! Add to advice or doctor_notes.
3. COMPLAINTS:
   - Extract symptom names ONLY (e.g. "fever", "cough", "headache"). NEVER include duration in complaints ("for 3 days" belongs to duration or notes, not the complaint string).
4. DIAGNOSES:
   - Extract all mentioned clinical conditions, provisional diagnoses, and chronic comorbidities (e.g. "URTI", "Otitis Media", "Type 2 Diabetes Mellitus", "Hypertension", "Pneumonia", "GERD", "Dengue Fever").
5. INVESTIGATIONS:
   - Include all blood tests, radiology, scans, cultures (e.g. CBC, Widal, Chest X-ray, Ultrasound, Urine Routine, HbA1c, ECG, 2D Echo).
6. ANTI-HALLUCINATION:
   - Only extract information present in the transcript. Output empty lists [] or empty strings "" if a category was not discussed."""

_FEW_SHOT_EXAMPLE = """--- Example 1 ---
Transcript: "Patient has high fever for 3 days and severe dry cough. Acute bronchitis. Prescribe Augmentin 625mg twice daily for 5 days and Dolo 650mg thrice daily for 3 days. Do a CBC test. Drink warm water. Review in 1 week."
Output:
{
  "complaints": ["fever", "dry cough"],
  "diagnosis": ["Acute Bronchitis"],
  "medications": [
    {"name": "Augmentin", "dose": "625mg", "frequency": "BD", "duration": "5 days", "route": "Oral", "instructions": "Take after food"},
    {"name": "Dolo", "dose": "650mg", "frequency": "TID", "duration": "3 days", "route": "Oral", "instructions": "Take after food"}
  ],
  "investigations": ["CBC"],
  "advice": ["Drink warm water"],
  "follow_up": "Follow up in 1 week"
}

--- Example 2 (Negative warnings & Indian Brands) ---
Transcript: "Dengue fever NS1 positive. Severe body ache and headache. Prescribe Dolo 650mg every 6 hours SOS. Strictly avoid aspirin and ibuprofen. Daily platelet count. Drink tender coconut water and ORS. Review in 2 days."
Output:
{
  "complaints": ["body ache", "headache"],
  "diagnosis": ["Dengue Fever"],
  "medications": [
    {"name": "Dolo", "dose": "650mg", "frequency": "QID", "duration": "", "route": "Oral", "instructions": "Take as needed (SOS)"}
  ],
  "investigations": ["platelet count"],
  "advice": ["Avoid aspirin and ibuprofen", "Drink tender coconut water and ORS"],
  "follow_up": "Review in 2 days"
}

--- Example 3 (Inhalers, Sprays, Drops & Chronic Care) ---
Transcript: "Known case of hypertension and bronchial asthma. BP is 150/90. Prescribe Telma 40mg once daily in morning, Foracort 200 inhaler 2 puffs twice daily, and Ciplox ear drops 3 drops thrice daily for right ear. Stop smoking. Review in 2 weeks."
Output:
{
  "complaints": [],
  "diagnosis": ["Hypertension", "Bronchial Asthma"],
  "medications": [
    {"name": "Telma", "dose": "40mg", "frequency": "OD", "duration": "", "route": "Oral", "instructions": "Take in the morning"},
    {"name": "Foracort", "dose": "200mcg", "frequency": "BD", "duration": "", "route": "Inhaled", "instructions": "Rinse mouth after inhalation"},
    {"name": "Ciplox", "dose": "3 drops", "frequency": "TID", "duration": "", "route": "Otic", "instructions": "Instill in right ear"}
  ],
  "investigations": [],
  "advice": ["Stop smoking"],
  "follow_up": "Review in 2 weeks"
}"""


# ── Model Management ──────────────────────────────────────

def is_available(model_key: str | None = None) -> bool:
    """Check if LLM refinement is enabled and the specified/active model exists."""
    if not LLM_ENABLED:
        return False
    path = get_model_path(model_key)
    if not os.path.isfile(path):
        logger.info("LLM refinement enabled but model file not found at %s", path)
        return False
    try:
        from llama_cpp import Llama  # noqa: F401
        return True
    except ImportError:
        logger.warning("llama-cpp-python not installed. LLM refinement unavailable.")
        return False


def load_model(model_key: str | None = None):
    """Lazy-load the GGUF model. Thread-safe, cached after first call."""
    global _llm_model, _loaded_model_key
    target_key = model_key or _active_model_key

    with _llm_lock:
        # If target model is already loaded, return it
        if _llm_model is not None and _loaded_model_key == target_key:
            return _llm_model

        # If a different model is loaded, unload it first
        if _llm_model is not None and _loaded_model_key != target_key:
            logger.info("Unloading previous model %s to load %s", _loaded_model_key, target_key)
            unload_model()

        if not is_available(target_key):
            return None

        from llama_cpp import Llama

        model_path = get_model_path(target_key)
        logger.info("Loading LLM model [%s] from %s ...", target_key, model_path)
        start = time.time()

        _llm_model = Llama(
            model_path=model_path,
            n_gpu_layers=LLM_N_GPU_LAYERS,
            n_threads=LLM_N_THREADS,
            n_ctx=LLM_CONTEXT_SIZE,
            n_batch=512,
            logits_all=False,
            verbose=False,
        )
        _loaded_model_key = target_key

        elapsed = time.time() - start
        logger.info("LLM model [%s] loaded in %.1fs", target_key, elapsed)
        return _llm_model


def unload_model():
    """Free the LLM from memory (for model-swapping on edge devices)."""
    global _llm_model, _loaded_model_key
    with _llm_lock:
        if _llm_model is not None:
            del _llm_model
            _llm_model = None
            _loaded_model_key = None
            logger.info("LLM model unloaded from memory.")


# ── Prompt Construction ───────────────────────────────────

def _build_prompt(transcript: str, draft_entities: dict) -> str:
    """Build the focused extraction prompt with draft entities for correction."""
    draft_json = json.dumps(_sanitize_draft(draft_entities), ensure_ascii=False, separators=(",", ":"))

    max_transcript_chars = 1200
    if len(transcript) > max_transcript_chars:
        transcript = "..." + transcript[-max_transcript_chars:]

    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"{_FEW_SHOT_EXAMPLE}\n\n"
        f"Draft extraction: {draft_json}\n\n"
        f"Transcript: \"{transcript}\"\n"
        f"Output JSON:"
    )
    return prompt


def _build_messages(transcript: str, draft_entities: dict) -> list[dict]:
    """Build ChatML messages array for create_chat_completion."""
    draft_json = json.dumps(_sanitize_draft(draft_entities), ensure_ascii=False, separators=(",", ":"))

    max_transcript_chars = 1200
    if len(transcript) > max_transcript_chars:
        transcript = "..." + transcript[-max_transcript_chars:]

    system_content = f"{_SYSTEM_PROMPT}\n\n{_FEW_SHOT_EXAMPLE}"
    user_content = (
        f"Draft extraction (may have errors): {draft_json}\n\n"
        f"Transcript: \"{transcript}\"\n\n"
        f"Output JSON:"
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _sanitize_draft(entities: dict) -> dict:
    """Strip internal metadata from draft entities before sending to LLM."""
    sanitized = {}

    sanitized["complaints"] = [
        c.get("name", c) if isinstance(c, dict) else str(c)
        for c in entities.get("complaints", [])
    ]
    sanitized["diagnosis"] = entities.get("diagnosis", [])

    sanitized["medications"] = []
    for med in entities.get("medications", []):
        sanitized["medications"].append({
            "name": med.get("name", ""),
            "dose": med.get("dose", ""),
            "frequency": med.get("frequency", ""),
            "duration": med.get("duration", ""),
        })

    sanitized["investigations"] = entities.get("investigations", [])
    sanitized["advice"] = entities.get("advice", [])
    sanitized["follow_up"] = entities.get("follow_up", "")

    return sanitized


# ── Response Parsing ──────────────────────────────────────

def _repair_json_string(text: str) -> str:
    """Repair common small-LLM JSON defects (trailing commas, single quotes, unquoted keys)."""
    # Remove trailing commas before closing braces/brackets
    s = re.sub(r",\s*([\]}])", r"\1", text)
    # Fix single quotes around keys or strings
    s = re.sub(r"(?<=[\{\s,])'([a-zA-Z0-9_\-]+)':", r'"\1":', s)
    s = re.sub(r":\s*'([^']*)'", r': "\1"', s)
    return s


def _normalize_parsed_dict(data: dict) -> dict:
    """Normalize common singular/plural and alias key variations produced by small LLMs."""
    normalized = {}

    # Complaints
    complaints = data.get("complaints") or data.get("complaint") or data.get("symptoms") or []
    if isinstance(complaints, str):
        complaints = [complaints]
    normalized["complaints"] = complaints

    # Diagnosis
    diagnosis = data.get("diagnosis") or data.get("diagnoses") or data.get("condition") or data.get("conditions") or []
    if isinstance(diagnosis, str):
        diagnosis = [diagnosis]
    normalized["diagnosis"] = diagnosis

    # Medications
    meds = data.get("medications") or data.get("medication") or data.get("drugs") or data.get("medicines") or data.get("rx") or []
    if isinstance(meds, dict):
        meds = [meds]
    normalized["medications"] = meds

    # Investigations
    inv = data.get("investigations") or data.get("investigation") or data.get("tests") or data.get("labs") or []
    if isinstance(inv, str):
        inv = [inv]
    normalized["investigations"] = inv

    # Advice
    advice = data.get("advice") or data.get("advise") or data.get("instructions") or data.get("lifestyle") or []
    if isinstance(advice, str):
        advice = [advice]
    normalized["advice"] = advice

    # Follow-up
    normalized["follow_up"] = data.get("follow_up") or data.get("followup") or data.get("follow_up_advice") or data.get("review") or ""

    return normalized


def _parse_llm_response(raw_text: str) -> dict | None:
    """Parse LLM output as JSON with robust multi-tier repair for small models like TinyLlama."""
    if not raw_text:
        return None

    text = raw_text.strip()

    # Strip markdown code fences if present (```json ... ```)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Tier 1: Direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            raw_dict = data.get("prescription", data)
            return _normalize_parsed_dict(raw_dict)
    except Exception:
        pass

    # Tier 2: Extract outermost balanced { ... }
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        brace_end = -1
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break

        if brace_end != -1:
            candidate = text[brace_start:brace_end + 1]
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    raw_dict = data.get("prescription", data)
                    return _normalize_parsed_dict(raw_dict)
            except Exception:
                pass

            # Tier 3: Heuristic string repair
            repaired = _repair_json_string(candidate)
            try:
                data = json.loads(repaired)
                if isinstance(data, dict):
                    raw_dict = data.get("prescription", data)
                    return _normalize_parsed_dict(raw_dict)
            except Exception:
                pass

    return None


# ── Drug Validation ───────────────────────────────────────

def _validate_medications(medications: list) -> list:
    """Validate LLM-suggested medications against the drug catalog.
    Rejects hallucinated names not in the dictionary or failing fuzzy match.
    Auto-enriches route and instructions from the catalog if the LLM left them empty.
    """
    validated = []
    seen = set()

    for med in medications:
        if not isinstance(med, dict):
            continue

        name = med.get("name", "").strip()
        if not name or len(name) < 2:
            continue

        name_lower = name.lower()
        if name_lower in NON_MEDICINAL_WORDS:
            continue

        # Validate against drug catalog
        match = fuzzy_match_drug(name)
        if match:
            # Preserve the doctor's spoken brand name if valid, otherwise use normalized generic
            canonical = name.strip() if len(name.strip()) >= 3 else match["normalized"]
        elif is_valid_medicine_token(name):
            canonical = name.title()
        else:
            canonical = name.title()
            med["needs_review"] = True

        canonical_key = canonical.lower()
        if canonical_key in seen:
            continue
        seen.add(canonical_key)

        # Auto-enrich route and instructions from catalog if LLM left them empty
        llm_route = med.get("route", "").strip()
        llm_instructions = med.get("instructions", "").strip()
        if not llm_route or not llm_instructions:
            catalog_info = get_route_and_instructions(name)
            if not llm_route and catalog_info["route"]:
                llm_route = catalog_info["route"]
            if not llm_instructions and catalog_info["instructions"]:
                llm_instructions = catalog_info["instructions"]

        validated.append({
            "name": canonical,
            "dose": med.get("dose", ""),
            "frequency": med.get("frequency", ""),
            "duration": med.get("duration", ""),
            "route": llm_route,
            "instructions": llm_instructions,
            "needs_review": med.get("needs_review", False),
        })

    return validated


def _validate_complaints(complaints: list) -> list:
    """Ensure complaints are simple symptom names without duration."""
    validated = []
    seen = set()

    for c in complaints:
        if isinstance(c, dict):
            name = c.get("name", "")
        else:
            name = str(c)

        name = name.strip().lower()
        if name and name not in seen:
            seen.add(name)
            validated.append({"name": name, "duration": ""})

    return validated


# ── Merge Strategy ────────────────────────────────────────

def _merge_entities(draft: dict, refined: dict) -> dict:
    """Merge LLM-refined entities with draft, preferring LLM for structure
    but keeping dictionary-validated drug names.
    """
    merged = {}

    # Complaints: union of both sets
    draft_complaints = {(c.get("name", "") if isinstance(c, dict) else str(c)).lower() for c in draft.get("complaints", [])}
    refined_complaints = _validate_complaints(refined.get("complaints", []))
    all_complaint_names = set()
    all_complaints = []

    for c in refined_complaints:
        key = c["name"].lower()
        if key not in all_complaint_names:
            all_complaint_names.add(key)
            all_complaints.append(c)

    for c in draft.get("complaints", []):
        name = (c.get("name", "") if isinstance(c, dict) else str(c)).lower()
        if name and name not in all_complaint_names:
            all_complaint_names.add(name)
            all_complaints.append({"name": name, "duration": ""})

    merged["complaints"] = all_complaints

    # Diagnosis: union
    draft_diag = set(d.lower() for d in draft.get("diagnosis", []))
    refined_diag = refined.get("diagnosis", [])
    all_diag = list(refined_diag)
    for d in draft.get("diagnosis", []):
        if d.lower() not in {r.lower() for r in refined_diag}:
            all_diag.append(d)
    merged["diagnosis"] = all_diag

    # Medications: If LLM produced validated medications, trust LLM as primary
    # (prevents re-injecting words doctor warned against or generic synonyms already covered by brand)
    refined_meds = _validate_medications(refined.get("medications", []))
    draft_meds = draft.get("medications", [])
    
    if refined_meds:
        # LLM successfully extracted medications: Use LLM list as authoritative
        from clinical.medicines import lookup
        all_meds = list(refined_meds)
        
        # Build set of covered brands and generic equivalents
        covered_names = set()
        for rm in refined_meds:
            r_name = rm.get("name", "").lower().strip()
            covered_names.add(r_name)
            r_info = lookup(r_name)
            if r_info and r_info.get("generic"):
                covered_names.add(r_info["generic"].lower().strip())
                for comp in r_info["generic"].lower().split("+"):
                    covered_names.add(comp.strip())

        # Only add draft meds if clearly an unextracted distinct compound
        for dm in draft_meds:
            dm_name = dm.get("name", "").strip()
            dm_lower = dm_name.lower()
            dm_info = lookup(dm_name)
            dm_generic = dm_info.get("generic", "").lower().strip() if dm_info else ""

            already_covered = (
                dm_lower in covered_names or
                (dm_generic and dm_generic in covered_names) or
                any(dm_lower in cov for cov in covered_names) or
                any(cov in dm_lower for cov in covered_names)
            )
            if not already_covered and len(dm_name) >= 3:
                all_meds.append(dm)
    else:
        # Fallback to draft medications if LLM produced no valid medications
        all_meds = list(draft_meds)

    merged["medications"] = all_meds

    # Investigations: union
    draft_inv = set(i.lower() for i in draft.get("investigations", []))
    refined_inv = refined.get("investigations", [])
    all_inv = list(refined_inv)
    for i in draft.get("investigations", []):
        if i.lower() not in {r.lower() for r in refined_inv}:
            all_inv.append(i)
    merged["investigations"] = all_inv

    # Advice: prefer LLM if non-empty, else draft
    merged["advice"] = refined.get("advice") or draft.get("advice", [])

    # Follow-up: prefer LLM if non-empty
    merged["follow_up"] = refined.get("follow_up") or draft.get("follow_up", "")

    # Preserve doctor_notes from draft
    merged["doctor_notes"] = draft.get("doctor_notes", "")

    return merged


# ── Public API ────────────────────────────────────────────

def refine(transcript: str, draft_entities: dict, model_key: str | None = None) -> dict:
    """Refine draft clinical entities using the LLM.

    This is the single public entry point. Called once per consultation
    when the user generates a prescription.

    Returns refined entities dict, or draft_entities unchanged on any failure.
    """
    target_key = model_key or _active_model_key
    if target_key == "disabled" or not is_available(target_key):
        logger.info("LLM refinement skipped for model [%s] (disabled or unavailable).", target_key)
        return draft_entities

    try:
        with _llm_lock:
            model = load_model(target_key)
            if model is None:
                return draft_entities

            messages = _build_messages(transcript, draft_entities)

            logger.info("Running LLM refinement via model [%s]...", target_key)
            start = time.time()

            response = model.create_chat_completion(
                messages=messages,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
            )

            raw_output = response["choices"][0]["message"]["content"] if response.get("choices") else ""
            elapsed = time.time() - start
            logger.info("LLM generation completed in %.1fs (%d output chars)", elapsed, len(raw_output))

            # Parse the response
            refined = _parse_llm_response(raw_output)
            if refined is None:
                logger.warning("Failed to parse LLM output as JSON. Using draft entities.")
                return draft_entities

            # Merge with draft (LLM fills gaps, dictionary validates drugs)
            merged = _merge_entities(draft_entities, refined)
            return merged

    except Exception as e:
        logger.error("LLM refinement encountered error: %s. Safely falling back to draft extraction.", e, exc_info=True)
        return draft_entities


def get_status() -> dict:
    """Return current LLM status and available models for the UI."""
    active_path = get_model_path(_active_model_key)
    model_exists = os.path.isfile(active_path)
    try:
        from llama_cpp import Llama  # noqa: F401
        lib_installed = True
    except ImportError:
        lib_installed = False

    active_info = LLM_MODELS.get(_active_model_key, {})
    model_name = active_info.get("name", _active_model_key)

    return {
        "enabled": LLM_ENABLED,
        "active_model_key": _active_model_key,
        "active_model_name": model_name,
        "active_model_ram": active_info.get("ram_mb", 0),
        "model_exists": model_exists,
        "lib_installed": lib_installed,
        "model_loaded": _llm_model is not None and _loaded_model_key == _active_model_key,
        "loaded_model_key": _loaded_model_key,
        "active": LLM_ENABLED and model_exists and lib_installed,
        "model_name": model_name,
        "available_models": list_available_models(),
    }
