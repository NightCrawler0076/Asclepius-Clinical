"""
Whisper ASR engine — model caching, clinical vocabulary injection, and transcription.
"""

import logging
import os
import threading

from config import (
    DEFAULT_MODEL, MODEL_SIZES, ASR_BACKEND, ASR_COMPUTE_TYPE, ASR_BEAM_SIZE,
    LLM_N_THREADS, WHISPER_MODEL_DIR,
)

logger = logging.getLogger(__name__)

_model_cache: dict = {}
_model_lock = threading.Lock()


def _resolve_backend() -> str:
    """Pick the ASR backend. 'auto' prefers faster-whisper (fast int8 on ARM/x86 CPUs)."""
    if ASR_BACKEND in ("faster-whisper", "openai-whisper"):
        return ASR_BACKEND
    try:
        import faster_whisper  # noqa: F401
        return "faster-whisper"
    except ImportError:
        return "openai-whisper"


BACKEND = _resolve_backend()

# faster-whisper names the large model "large-v3"
_FW_MODEL_NAMES = {"large": "large-v3"}

# Clinical initial prompt primes Whisper attention on medical pharmacology & terminology.
# Whisper's conditioning window accepts up to 224 prompt tokens. It biases beam search
# toward exact medical spelling (e.g. 'Augmentin 625', 'Dolo 650', 'Pan-D', 'OD/BD/TDS',
# '500 mg', 'HbA1c', 'LFT/KFT') preventing phonetic transcript distortions.
CLINICAL_INITIAL_PROMPT = (
    # Doctor dictation style & common prescription header
    "Doctor's clinical consultation and Rx prescription note: "
    # Antibiotics, Antivirals & Antifungals
    "Amoxicillin, Augmentin 625, Amoxiclav, Clavum, Azithromycin, Azee 500, Zithromax, "
    "Ciprofloxacin, Cifran, Cefixime, Zifi 200, Taxim-O, Cefpodoxime, Cefuroxime, Ceftriaxone, "
    "Ofloxacin, Oflox-OZ, Norflox-TZ, Metronidazole, Flagyl, Doxycycline, Nitrofurantoin, "
    "Linezolid, Fluconazole, Acyclovir, "
    # Analgesics, Antipyretics, Antispasmodics & NSAIDs
    "Paracetamol, PCM, Dolo 650, Crocin, Calpol, Ibuprofen, Brufen, Combiflam, Flexon, "
    "Diclofenac, Voveran, Aceclofenac, Zerodol-P, Zerodol-SP, Mefenamic acid, Meftal-Spas, "
    "Drotaverine, Drotin-M, Tramadol, Ultracet, Etoricoxib, Nucoxia, Aspirin, Ecosprin 75, "
    # Gastroenterology & Antacids (PPIs / Prokinetics)
    "Pantoprazole, Pan-D, Pan-40, Omeprazole, Omez, Rabeprazole, Razo-D, Esomeprazole, Nexpro, "
    "Ranitidine, Ondansetron, Emset, Domperidone, Domstal, Metoclopramide, Sucralfate, Digene, "
    "Cremaffin, ORS, Electral, "
    # Respiratory, Antiallergic & ENT
    "Cetirizine, Levocetirizine, Levocet, Allegra 120, Montelukast, Montair-LC, Montek-LC, "
    "Salbutamol, Asthalin, Budesonide, Budecort, Foracort, Seroflo, Dextromethorphan, "
    "Ambroxol, Ascoril, Benadryl, Alex, Grilinctus, "
    # Cardiology, Antihypertensives, Diabetes, Thyroid & Statins
    "Amlodipine, Telmisartan, Telma 40, Atenolol, Metoprolol, Ramipril, Enalapril, Losartan, "
    "Furosemide, Lasix, Spironolactone, Atorvastatin, Rosuvastatin, Metformin, Glycomet 500, "
    "Glimepiride, Amaryl, Teneligliptin, Dapagliflozin, Insulin, Thyroxine, Eltroxin, "
    # Dosage forms, strengths and units
    "tab, tablet, cap, capsule, syrup, drops, injection, IV, IM, puff, inhaler, sachet, ointment, "
    "650 mg, 500 mg, 250 mg, 100 mg, 50 mg, 40 mg, 20 mg, 10 mg, 5 mg, 1 g, 5 ml, 10 ml, "
    "mcg, microgram, IU, units, "
    # Frequencies & timings
    "OD, BD, TDS, TID, QID, SOS, STAT, PRN, HS, 1-0-0, 0-1-0, 0-0-1, 1-0-1, 1-1-1, "
    "once daily, twice daily, thrice daily, four times daily, as needed, at bedtime, "
    "before food, after food, empty stomach, with meals, "
    # Duration
    "for 3 days, for 5 days, for 7 days, for 10 days, for 2 weeks, for 1 month, "
    # Common investigations & clinical labs
    "CBC, Hb, TLC, DLC, Platelets, ESR, HbA1c, FBS, PPBS, RBS, Lipid profile, "
    "LFT, SGOT, SGPT, Bilirubin, KFT, Serum Creatinine, Blood Urea, Urine R/M, "
    "TSH, ECG, 2D Echo, Chest X-ray, USG Abdomen, CT, MRI, Dengue NS1, Widal, "
    # Clinical signs, diagnoses & advice
    "BP, PR, SpO2, Temp, URTI, acute bronchitis, gastroenteritis, GERD, migraine, "
    "hypertension, type 2 diabetes mellitus, dyslipidemia, review after 3 days."
)


def _validate_size(model_size: str | None) -> str:
    if model_size not in MODEL_SIZES:
        logger.warning("Whisper model '%s' not allowed on this device; using '%s'", model_size, DEFAULT_MODEL)
        return DEFAULT_MODEL
    return model_size


def _find_local_whisper_dir(model_size: str) -> str | None:
    """Check if the model was already pre-downloaded in models/whisper."""
    fw_name = _FW_MODEL_NAMES.get(model_size, model_size)
    candidates = [
        f"faster-whisper-{fw_name}",
        f"faster-whisper-{model_size}",
        fw_name,
        model_size,
    ]
    for c in candidates:
        candidate_dir = os.path.join(WHISPER_MODEL_DIR, c)
        if os.path.isdir(candidate_dir):
            if os.path.isfile(os.path.join(candidate_dir, "model.bin")) or \
               os.path.isfile(os.path.join(candidate_dir, "model.safetensors")):
                return candidate_dir
    return None


def load_model(model_size: str = DEFAULT_MODEL):
    """Load and cache a Whisper model.
    If the model exists in models/whisper, it is loaded from disk.
    If not, it will be downloaded on first use into models/whisper.
    """
    model_size = _validate_size(model_size)
    with _model_lock:
        if model_size not in _model_cache:
            print(f"Loading Whisper model '{model_size}' via {BACKEND}...")
            if BACKEND == "faster-whisper":
                from faster_whisper import WhisperModel
                local_dir = _find_local_whisper_dir(model_size)
                if local_dir:
                    print(f"Using pre-downloaded Whisper model from: {local_dir}")
                    source = local_dir
                else:
                    fw_name = _FW_MODEL_NAMES.get(model_size, model_size)
                    print(f"Whisper model '{model_size}' not in {WHISPER_MODEL_DIR}. Downloading '{fw_name}'...")
                    source = fw_name
                _model_cache[model_size] = WhisperModel(
                    source,
                    device="cpu",
                    compute_type=ASR_COMPUTE_TYPE,
                    cpu_threads=LLM_N_THREADS,
                    download_root=WHISPER_MODEL_DIR,
                )
            else:
                import whisper
                _model_cache[model_size] = whisper.load_model(model_size, download_root=WHISPER_MODEL_DIR)
            print("Model loaded.")
        return _model_cache[model_size]


def _transcribe_faster_whisper(model, audio_path: str) -> dict:
    segments_iter, info = model.transcribe(
        audio_path,
        initial_prompt=CLINICAL_INITIAL_PROMPT,
        temperature=0.0,
        beam_size=ASR_BEAM_SIZE,
        vad_filter=True,  # skip silence — big speed win on CPU
    )
    segments, texts = [], []
    for seg in segments_iter:  # generator: decoding happens here
        text = seg.text.strip()
        texts.append(text)
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": text,
            "confidence": seg.avg_logprob,
        })
    return {"text": " ".join(texts).strip(), "language": info.language, "segments": segments}


def _transcribe_openai_whisper(model, audio_path: str) -> dict:
    result = model.transcribe(
        audio_path,
        initial_prompt=CLINICAL_INITIAL_PROMPT,
        temperature=0.0,
        fp16=(str(getattr(model, "device", "cpu")) != "cpu"),  # fp32 on CPU (Pi)
    )
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg.get("start", 0.0),
            "end": seg.get("end", 0.0),
            "text": seg.get("text", "").strip(),
            "confidence": seg.get("avg_logprob", None),
        })
    return {
        "text": result.get("text", "").strip(),
        "language": result.get("language", ""),
        "segments": segments,
    }


def transcribe(audio_path: str, model_size: str = DEFAULT_MODEL) -> dict:
    """Transcribe an audio file using Whisper with clinical vocabulary priming.

    Returns dict with keys:
        text: str — full transcript
        language: str — detected language
        segments: list — segment-level details from Whisper
    """
    model_size = _validate_size(model_size)
    model = load_model(model_size)
    if BACKEND == "faster-whisper":
        result = _transcribe_faster_whisper(model, audio_path)
    else:
        result = _transcribe_openai_whisper(model, audio_path)
    result["model_used"] = model_size
    return result
