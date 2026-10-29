"""
System / device audio (loopback) capture — extracted from the original monolith.
"""

import sys
import threading

import numpy as np
import scipy.io.wavfile as wav
import soundcard as sc

from config import SAMPLE_RATE, BLOCK_SIZE, SYSTEM_WAV_PATH

# ── COM helper (Windows) ──────────────────────────────────
if sys.platform == "win32":
    import comtypes

    def ensure_com():
        try:
            comtypes.CoInitialize()
        except OSError:
            pass
else:
    def ensure_com():
        pass


# ── Shared state ───────────────────────────────────────────
_state = {
    "recording": False,
    "frames": [],
    "thread": None,
    "stop_event": None,
    "error": None,
}
_lock = threading.Lock()


def _get_loopback_mic(device_name: str | None = None):
    """Grab a loopback 'microphone' that mirrors a speaker's output."""
    ensure_com()
    if device_name:
        speaker = sc.get_speaker(device_name)
    else:
        speaker = sc.default_speaker()
    try:
        return sc.get_microphone(id=speaker.id, include_loopback=True)
    except Exception:
        return sc.get_microphone(speaker.name, include_loopback=True)


def _record_loop(device_name: str | None, stop_event: threading.Event):
    """Background thread: capture audio until stop_event is set."""
    try:
        loopback_mic = _get_loopback_mic(device_name)
        with loopback_mic.recorder(samplerate=SAMPLE_RATE, channels=1) as recorder:
            while not stop_event.is_set():
                data = recorder.record(numframes=BLOCK_SIZE)
                _state["frames"].append(data.copy())
    except Exception as e:
        _state["error"] = str(e)


def list_output_devices() -> list[dict]:
    """Return [{name, default}, …] for every output device."""
    ensure_com()
    speakers = sc.all_speakers()
    default_id = sc.default_speaker().id
    return [{"name": s.name, "default": s.id == default_id} for s in speakers]


def start(device_name: str | None = None) -> None:
    with _lock:
        if _state["recording"]:
            raise RuntimeError("Already capturing")

        _state["frames"] = []
        _state["error"] = None
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_record_loop, args=(device_name, stop_event), daemon=True
        )
        _state["stop_event"] = stop_event
        _state["thread"] = thread
        _state["recording"] = True
        thread.start()


def stop() -> str:
    """Stop capturing. Returns the path to the saved WAV file."""
    with _lock:
        if not _state["recording"]:
            raise RuntimeError("Not currently capturing")
        _state["recording"] = False
        stop_event = _state["stop_event"]
        thread = _state["thread"]

    if stop_event is not None:
        stop_event.set()
    if thread is not None:
        thread.join(timeout=5)

    if _state["error"]:
        raise RuntimeError(_state["error"])

    frames = _state["frames"]
    if not frames:
        raise ValueError(
            "No audio was captured. Make sure something was actually playing."
        )

    audio = np.concatenate(frames, axis=0)
    audio_clipped = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio_clipped * 32767).astype(np.int16)
    wav.write(SYSTEM_WAV_PATH, SAMPLE_RATE, audio_int16)
    return SYSTEM_WAV_PATH
