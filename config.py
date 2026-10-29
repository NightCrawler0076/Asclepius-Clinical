"""
Configuration for Doctor Voice-to-Prescription System
"""

import os
import tempfile

# ── Paths ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "database.sqlite")

# Ensure data directories exist
for subdir in ["doctors", "patients", "consultations"]:
    os.makedirs(os.path.join(DATA_DIR, subdir), exist_ok=True)

TMP_DIR = tempfile.gettempdir()
MIC_WAV_PATH = os.path.join(TMP_DIR, "recording_mic.wav")
SYSTEM_WAV_PATH = os.path.join(TMP_DIR, "recording_system_audio.wav")


# ── Platform detection ─────────────────────────────────────
def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _detect_raspberry_pi() -> bool:
    try:
        with open("/proc/device-tree/model", "r", encoding="utf-8", errors="ignore") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
        return False


IS_RASPBERRY_PI = _env_bool("EMB_FORCE_PI", _detect_raspberry_pi())

# ── Audio ──────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024

# System/loopback capture is a desktop feature; off by default on the Pi.
ENABLE_SYSTEM_AUDIO = _env_bool("EMB_ENABLE_SYSTEM_AUDIO", not IS_RASPBERRY_PI)

# ── ASR / Whisper ──────────────────────────────────────────
# Backend: "faster-whisper" (CTranslate2, int8 — much faster on ARM CPUs)
# or "openai-whisper" (PyTorch). "auto" prefers faster-whisper if installed.
ASR_BACKEND = os.environ.get("EMB_ASR_BACKEND", "auto")
ASR_COMPUTE_TYPE = os.environ.get("EMB_ASR_COMPUTE_TYPE", "int8")  # faster-whisper only
ASR_BEAM_SIZE = int(os.environ.get("EMB_ASR_BEAM_SIZE", "1" if IS_RASPBERRY_PI else "5"))

# Available Whisper model sizes across desktop and 8GB Raspberry Pi 5
MODEL_SIZES = ["base", "small", "medium"]
DEFAULT_MODEL = os.environ.get("EMB_WHISPER_MODEL", "small")

# ── Flask ──────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ── LLM Refinement ─────────────────────────────────────────
LLM_ENABLED = True                          # Master toggle for LLM post-processing
LLM_MODEL_DIR = os.path.join(BASE_DIR, "models")
LLM_MODEL_PATH = os.path.join(LLM_MODEL_DIR, "qwen2.5-1.5b-instruct-q4_k_m.gguf")

# LLM Model Registry
LLM_MODELS = {
    "qwen2.5-1.5b": {
        "id": "qwen2.5-1.5b",
        "name": "Qwen2.5 1.5B Instruct",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "description": "High clinical accuracy & precise JSON entity extraction (~1.1 GB RAM)",
        "ram_mb": 1100,
    },
    "llama-3.2-1b-medical": {
        "id": "llama-3.2-1b-medical",
        "name": "Llama 3.2 1B Medical",
        "filename": "Llama3.2-1B-Medical-Q4_KM.gguf",
        "description": "Clinical medical fine-tune for fast edge extraction (~800 MB RAM)",
        "ram_mb": 800,
    },
    "qwen2.5-3b-medical": {
        "id": "qwen2.5-3b-medical",
        "name": "Qwen2.5 3B Medical",
        "filename": "qwen2.5-3b-medical-instruct-q4_k_m.gguf",
        "description": "Clinical medical fine-tune with higher reasoning capacity (~2.2 GB RAM)",
        "ram_mb": 2200,
    },
}
DEFAULT_LLM_MODEL_KEY = os.environ.get("EMB_LLM_MODEL", "qwen2.5-1.5b")

LLM_N_GPU_LAYERS = 0                        # 0 = CPU execution (safe for edge / Pi / CPU builds)
LLM_N_THREADS = int(os.environ.get("EMB_LLM_THREADS", "4"))  # Match target CPU core count (Pi 5 = 4)
LLM_MAX_TOKENS = 512                        # Cap output generation length
LLM_CONTEXT_SIZE = 2048                     # Context window for local models
LLM_TEMPERATURE = 0.0                       # Greedy decoding for determinism

os.makedirs(LLM_MODEL_DIR, exist_ok=True)

# Pre-downloaded faster-whisper models (offline install):
#   models/whisper/faster-whisper-<size>/{model.bin, config.json, tokenizer.json, vocabulary.txt}
# If a folder exists it is used instead of downloading from Hugging Face.
WHISPER_MODEL_DIR = os.path.join(LLM_MODEL_DIR, "whisper")


