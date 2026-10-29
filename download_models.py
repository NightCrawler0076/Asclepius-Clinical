"""
Download and Package Models for Raspberry Pi 5 (Offline Plug-and-Play)
========================================================================
This script runs on your PC (with internet connection) and downloads:
  1. faster-whisper-medium (~1.4 GB) -> models/whisper/faster-whisper-medium/
  2. faster-whisper-small  (~466 MB) -> models/whisper/faster-whisper-small/
  3. faster-whisper-base   (~142 MB) -> models/whisper/faster-whisper-base/
  4. Qwen2.5-1.5B-Instruct (~1.06 GB)-> models/qwen2.5-1.5b-instruct-q4_k_m.gguf
  5. Llama-3.2-1B-Medical  (~770 MB) -> models/Llama3.2-1B-Medical-Q4_KM.gguf
  6. Qwen2.5-3B-Medical    (~1.84 GB)-> models/qwen2.5-3b-medical-instruct-q4_k_m.gguf

It also:
  - Cleans up any deprecated models (Whisper tiny, large, TinyLlama).
  - Verifies all model files exist and match requirements.
  - Ensures the entire models/ folder is ready to copy/paste to the Pi.
"""

import os
import sys
import shutil
import urllib.request

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("Installing huggingface_hub...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
    from huggingface_hub import snapshot_download


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
WHISPER_DIR = os.path.join(MODELS_DIR, "whisper")


# ── 1. Clean up Deprecated Models ──────────────────────────────────────────
def cleanup_deprecated_models():
    tiny_dir = os.path.join(WHISPER_DIR, "faster-whisper-tiny")
    if os.path.exists(tiny_dir):
        print(f"[*] Removing old whisper-tiny directory: {tiny_dir}")
        shutil.rmtree(tiny_dir, ignore_errors=True)
        print("[+] Whisper tiny removed.")

    for large_name in ["faster-whisper-large-v3", "faster-whisper-large"]:
        large_dir = os.path.join(WHISPER_DIR, large_name)
        if os.path.exists(large_dir):
            print(f"[*] Removing whisper-large directory: {large_dir}")
            shutil.rmtree(large_dir, ignore_errors=True)
            print(f"[+] {large_name} removed.")

    tinyllama_file = os.path.join(MODELS_DIR, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
    if os.path.isfile(tinyllama_file):
        print(f"[*] Removing deprecated TinyLlama model: {tinyllama_file}")
        try:
            os.remove(tinyllama_file)
            print("[+] TinyLlama removed.")
        except Exception as e:
            print(f"[!] Could not remove TinyLlama: {e}")


# ── 2. Download faster-whisper Models ───────────────────────────────────────
WHISPER_MODELS = [
    ("faster-whisper-medium", "Systran/faster-whisper-medium"),
    ("faster-whisper-small", "Systran/faster-whisper-small"),
    ("faster-whisper-base", "Systran/faster-whisper-base"),
]

def download_whisper_models():
    os.makedirs(WHISPER_DIR, exist_ok=True)
    for folder_name, repo_id in WHISPER_MODELS:
        target_path = os.path.join(WHISPER_DIR, folder_name)
        model_bin = os.path.join(target_path, "model.bin")
        if os.path.isfile(model_bin):
            print(f"[+] {folder_name} already exists at {target_path} (skipping download).")
            continue

        print(f"\n[*] Downloading {repo_id} to {target_path}...")
        snapshot_download(
            repo_id=repo_id,
            local_dir=target_path,
            allow_patterns=["*.bin", "*.json", "*.txt"],
            local_dir_use_symlinks=False,  # CRITICAL for USB/FAT32 transfer to Raspberry Pi
        )
        print(f"[+] Successfully downloaded {folder_name}!")


# ── 3. Download LLM Models ──────────────────────────────────────────────────
QWEN_1_5B_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)
QWEN_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

LLAMA_MED_URL = (
    "https://huggingface.co/SandLogicTechnologies/Llama-3.2-1B-Instruct-Medical-GGUF/resolve/main/"
    "Llama3.2-1B-Medical-Q4_KM.gguf"
)
LLAMA_MED_FILENAME = "Llama3.2-1B-Medical-Q4_KM.gguf"

QWEN_3B_MED_URL = (
    "https://huggingface.co/mradermacher/Qwen2.5-3B-instruct-medical-finetuned-GGUF/resolve/main/"
    "Qwen2.5-3B-instruct-medical-finetuned.Q4_K_M.gguf"
)
QWEN_3B_MED_FILENAME = "qwen2.5-3b-medical-instruct-q4_k_m.gguf"

def download_llm_model():
    os.makedirs(MODELS_DIR, exist_ok=True)
    models_to_download = [
        (QWEN_FILENAME, QWEN_1_5B_URL),
        (LLAMA_MED_FILENAME, LLAMA_MED_URL),
        (QWEN_3B_MED_FILENAME, QWEN_3B_MED_URL),
    ]
    for name, url in models_to_download:
        dest_path = os.path.join(MODELS_DIR, name)
        if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 700 * 1024 * 1024:
            print(f"[+] {name} already exists ({os.path.getsize(dest_path) // (1024*1024)} MB). Skipping.")
            continue

        print(f"\n[*] Downloading {name}...")
        print(f"    From: {url}")

        def make_progress_hook(model_name):
            def progress_hook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = downloaded * 100 / total_size
                    mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    sys.stdout.write(f"\r    Downloading {model_name}: {mb:.1f} MB / {total_mb:.1f} MB ({percent:.1f}%)")
                    sys.stdout.flush()
            return progress_hook

        try:
            urllib.request.urlretrieve(url, dest_path, reporthook=make_progress_hook(name))
            print(f"\n[+] Successfully downloaded {name}!")
        except Exception as e:
            print(f"\n[!] Download error: {e}")


# ── 4. Verify Plug & Play Structure ─────────────────────────────────────────
def verify_offline_readiness():
    print("\n" + "=" * 65)
    print("VERIFYING MODELS FOR OFFLINE PLUG-AND-PLAY TRANSFER:")
    print("=" * 65)

    checks = [
        ("Whisper Medium (ASR)", os.path.join(WHISPER_DIR, "faster-whisper-medium", "model.bin")),
        ("Whisper Small (ASR)", os.path.join(WHISPER_DIR, "faster-whisper-small", "model.bin")),
        ("Whisper Base (ASR)", os.path.join(WHISPER_DIR, "faster-whisper-base", "model.bin")),
        ("Qwen2.5 1.5B (LLM)", os.path.join(MODELS_DIR, QWEN_FILENAME)),
        ("Llama 3.2 1B Med (LLM)", os.path.join(MODELS_DIR, LLAMA_MED_FILENAME)),
        ("Qwen2.5 3B Med (LLM)", os.path.join(MODELS_DIR, QWEN_3B_MED_FILENAME)),
    ]

    all_ok = True
    for name, path in checks:
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  [OK] {name:<24} -> {size_mb:.1f} MB ({os.path.basename(path)})")
        else:
            print(f"  [MISSING] {name:<24} -> Will download automatically on first use ({path})")
            all_ok = False

    print("=" * 65)
    if all_ok:
        print("\nAll models are present locally in models/ folder!")
    else:
        print("\nNote: Any missing models will automatically download from Hugging Face on first use.")


if __name__ == "__main__":
    print("=== Edge Medical AI: Model Packager ===")
    cleanup_deprecated_models()
    download_whisper_models()
    download_llm_model()
    verify_offline_readiness()
