"""Test Qwen2.5-3B-Medical model integration and clinical inference."""
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

    qwen_med = next((m for m in models if m["id"] == "qwen2.5-3b-medical"), None)
    assert qwen_med is not None, "qwen2.5-3b-medical not in list_available_models"
    assert qwen_med["file_exists"] is True, "qwen2.5-3b-medical file not found on disk"

    # Ensure tinyllama is completely gone
    tinyllama = next((m for m in models if m["id"] == "tinyllama-1.1b"), None)
    assert tinyllama is None, "tinyllama-1.1b should not be present in models list"

    print("\nActivating qwen2.5-3b-medical...")
    set_active_model("qwen2.5-3b-medical")
    status = get_status()
    print("Status:", json.dumps(status, indent=2))
    assert status["active_model_key"] == "qwen2.5-3b-medical"
    assert status["model_exists"] is True

    sample_transcript = (
        "Patient complains of persistent acid reflux and epigastric burning for two weeks. "
        "Diagnosed with GERD. Prescribing Pantocid 40mg once daily before breakfast for 14 days, "
        "and Gelusil MPS syrup 10ml thrice daily after meals for 7 days."
    )
    draft = {
        "complaints": ["acid reflux", "burning sensation"],
        "diagnosis": ["GERD"],
        "medications": [
            {"name": "Pantocid", "dose": "40mg", "frequency": "OD", "duration": "14 days", "timing": "before breakfast"},
            {"name": "Gelusil", "dose": "10ml", "frequency": "TID", "duration": "7 days", "timing": "after meals"},
        ],
        "advice": []
    }

    print("\nRunning refine() with Qwen2.5 3B Medical...")
    refined = refine(sample_transcript, draft)
    print("\nRefined Output:")
    print(json.dumps(refined, indent=2))

    assert "medications" in refined
    assert len(refined["medications"]) >= 2
    med_names = [m["name"].lower() for m in refined["medications"]]
    print("Extracted medications:", med_names)
    assert any("panto" in n or "pantocid" in n for n in med_names)
    assert any("gelusil" in n for n in med_names)

    # Reset back to default model
    print("\nResetting to qwen2.5-1.5b default...")
    set_active_model("qwen2.5-1.5b")
    unload_model()
    print("=== All tests for Qwen2.5-3B-Medical passed successfully! ===")

if __name__ == "__main__":
    main()
