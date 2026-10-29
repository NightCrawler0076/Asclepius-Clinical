"""Test Llama-3.2-1B-Instruct-Medical model integration and inference."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from clinical.llm_refiner import (
    list_available_models,
    set_active_model,
    refine,
    get_status,
    unload_model,
)

logging.basicConfig(level=logging.INFO)

def main():
    print("=== Available LLM Models ===")
    models = list_available_models()
    for m in models:
        print(f"  {m['id']}: exists={m['file_exists']}, size={m['file_size_mb']} MB, active={m['is_active']}")

    med_model = next((m for m in models if m["id"] == "llama-3.2-1b-medical"), None)
    assert med_model is not None, "llama-3.2-1b-medical not in list_available_models"
    assert med_model["file_exists"] is True, "llama-3.2-1b-medical file not found on disk"

    print("\nActivating llama-3.2-1b-medical...")
    set_active_model("llama-3.2-1b-medical")
    status = get_status()
    print("Status:", json.dumps(status, indent=2))
    assert status["active_model_key"] == "llama-3.2-1b-medical"
    assert status["model_exists"] is True

    sample_transcript = (
        "Patient presents with acute pharyngitis and bodyache. "
        "Advise Azithromycin 500mg once daily before food for 3 days, "
        "and Paracetamol 650mg TDS as needed for fever."
    )
    draft = {
        "complaints": ["bodyache"],
        "diagnosis": [],
        "medications": [
            {"name": "Azithromycin", "dose": "500mg", "frequency": "OD", "duration": "3 days", "timing": "before food"},
            {"name": "Paracetamol", "dose": "650mg", "frequency": "TID", "duration": "", "timing": ""},
        ],
        "advice": []
    }

    print("\nRunning refine() with sample clinical transcript...")
    refined = refine(sample_transcript, draft)
    print("\nRefined Output:")
    print(json.dumps(refined, indent=2))

    assert "medications" in refined
    assert len(refined["medications"]) >= 2
    med_names = [m["name"].lower() for m in refined["medications"]]
    print("Extracted medications:", med_names)
    assert any("azithromycin" in n for n in med_names)
    assert any("paracetamol" in n or "dolo" in n or "calpol" in n for n in med_names)

    # Reset back to default model
    print("\nResetting to qwen2.5-1.5b default...")
    set_active_model("qwen2.5-1.5b")
    unload_model()
    print("=== All tests for Llama-3.2-1B-Medical passed successfully! ===")

if __name__ == "__main__":
    main()
