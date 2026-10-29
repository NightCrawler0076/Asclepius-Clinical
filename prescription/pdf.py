"""
PDF prescription generation stub.

Phase 13 will use ReportLab for professional printable prescriptions.
"""

import json
import os

from config import DATA_DIR


def generate_pdf(prescription: dict) -> str:
    """Generate a PDF for the given prescription.

    Currently a stub — saves the prescription as a JSON file
    and returns its path. Phase 13 will generate a real PDF.
    """
    cons_id = prescription.get("consultation_id", "UNKNOWN")
    out_dir = os.path.join(DATA_DIR, "consultations", cons_id)
    os.makedirs(out_dir, exist_ok=True)

    # For now, save as JSON — PDF generation comes in Phase 13
    json_path = os.path.join(out_dir, "prescription.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(prescription, f, indent=2, ensure_ascii=False)

    return json_path
