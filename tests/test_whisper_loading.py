"""
Test Whisper local model loading and transcription verification.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asr.whisper_engine import load_model, _find_local_whisper_dir

def test_whisper_local_resolution():
    for size in ["small", "base", "medium"]:
        local_dir = _find_local_whisper_dir(size)
        assert local_dir is not None, f"Local directory for {size} not found"
        assert os.path.isfile(os.path.join(local_dir, "model.bin")), f"model.bin missing in {local_dir}"
        print(f"[OK] {size} resolves to local pre-downloaded folder: {local_dir}")

    # Verify that 'large' is correctly identified as not locally pre-downloaded
    large_dir = _find_local_whisper_dir("large")
    assert large_dir is None
    print("[OK] 'large' correctly reports as not pre-downloaded locally")

def test_whisper_load_small():
    print("Testing loading of Whisper 'small'...")
    model = load_model("small")
    assert model is not None
    print("[OK] Whisper 'small' successfully loaded from disk!")

if __name__ == "__main__":
    test_whisper_local_resolution()
    test_whisper_load_small()
    print("\nWHISPER TESTS PASSED CLEANLY!")
