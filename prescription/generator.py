"""
Prescription generator — orchestrates extraction → normalization → LLM refinement → schema.
"""

import logging

from clinical.extractor import extract
from clinical.normalizer import normalize_entities
from clinical.llm_refiner import refine as llm_refine, is_available as llm_is_available
from prescription.schema import new_prescription

logger = logging.getLogger(__name__)


def generate_from_transcript(
    transcript_text: str,
    doctor_id: str = "",
    patient: dict | None = None,
    llm_model_key: str | None = None,
) -> dict:
    """Generate a draft prescription from a transcript string.

    Pipeline: extract → normalize → LLM refine (if available) → build prescription.
    """
    # Step 1: Extract clinical entities (regex + dictionary)
    entities = extract(transcript_text)

    # Step 2: Normalize (phonetic + fuzzy drug matching)
    entities = normalize_entities(entities)

    # Step 3: LLM refinement (single call, optional)
    if llm_is_available(llm_model_key):
        logger.info("LLM refinement active (model: %s) — refining extracted entities...", llm_model_key or "default")
        entities = llm_refine(transcript_text, entities, model_key=llm_model_key)
    else:
        logger.info("LLM refinement not available for model [%s] — using dictionary extraction only.", llm_model_key)

    # Step 4: Clean medication normalization metadata
    cleaned_medications_list = []
    for raw_medication in entities.get("medications", []):
        clean_medication_dict = {key: val for key, val in raw_medication.items() if not key.startswith("_")}
        cleaned_medications_list.append(clean_medication_dict)

    # Step 5: Build prescription
    prescription_draft = new_prescription(
        doctor_id=doctor_id,
        patient=patient,
        complaints=entities.get("complaints", []),
        diagnosis=entities.get("diagnosis", []),
        medications=cleaned_medications_list,
        investigations=entities.get("investigations", []),
        advice=entities.get("advice", []),
        follow_up=entities.get("follow_up", ""),
        doctor_notes=entities.get("doctor_notes", ""),
    )

    return prescription_draft

