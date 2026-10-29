"""
Concurrency and thread-safety stress test for LLM refiner.
Verifies that multiple concurrent threads do not crash the C++ sampler or corrupt logits.
"""

import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinical.llm_refiner import refine


def test_concurrent_refinement():
    results = []
    errors = []

    def worker(idx):
        try:
            transcript = f"Patient {idx} complains of fever and headache. Prescribe Paracetamol 500mg BD for 5 days."
            draft = {"complaints": [{"name": "fever"}], "medications": []}
            res = refine(transcript, draft)
            results.append(res)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Encountered errors during concurrent execution: {errors}"
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    for res in results:
        assert isinstance(res, dict)
        assert len(res.get("medications", [])) >= 1
