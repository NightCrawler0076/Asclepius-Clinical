"""
Microphone recording — extracted from the original monolith with adaptive hardware stream negotiation.
"""

import sys
import threading

import numpy as np
import scipy.io.wavfile as wav
import scipy.signal
import sounddevice as sd

from config import SAMPLE_RATE, MIC_WAV_PATH

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


class MicRecorder:
    """Accumulates audio frames from a sounddevice InputStream."""

    def __init__(self, samplerate: int, channels: int):
        self.frames: list[np.ndarray] = []
        self.samplerate = samplerate
        self.channels = channels
        self.active = True


# ── Shared state ───────────────────────────────────────────
_state = {"recording": False, "recorder": None, "stream": None}
_lock = threading.Lock()


def _make_callback(recorder: MicRecorder):
    def callback(indata, frame_count, time_info, status):
        if status:
            print("Audio status:", status)
        if recorder.active:
            recorder.frames.append(indata.copy())
    return callback


def _clean_device_name(name: str) -> str:
    """Sanitize Windows device names by stripping newlines and raw driver path prefixes."""
    clean = " ".join(name.split())
    if ";(" in clean and clean.endswith(")"):
        friendly = clean.split(";(")[-1][:-1].strip()
        if friendly:
            return f"{friendly} (Bluetooth)"
    return clean


def list_input_devices() -> list[dict]:
    """Return [{id, name, default}, …] for every functional input device.

    Forces PortAudio to rescan the OS device list (when not actively recording)
    so hotplugged devices (e.g. a Bluetooth headset connected after app launch)
    are included.
    """
    ensure_com()
    with _lock:
        is_recording = _state["recording"]
    if not is_recording:
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    default_id = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else -1
    result = []
    
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            api_name = hostapis[d["hostapi"]]["name"] if d["hostapi"] < len(hostapis) else ""
            # Filter out WDM-KS endpoints which do not support standard blocking/callback streaming on Windows
            if "WDM-KS" in api_name:
                continue
                
            clean_name = _clean_device_name(d["name"])
            result.append({
                "id": i,
                "name": f"{clean_name} ({api_name})" if api_name else clean_name,
                "default": (i == default_id),
            })

    if sys.platform.startswith("linux"):
        result = _linux_order_and_label(result, devices)
    return result


# ALSA virtual devices routed through PipeWire/PulseAudio. Bluetooth mics are
# only reachable through these (they are not raw ALSA hw: devices).
_LINUX_VIRTUAL = ("default", "pipewire", "pulse")


def _linux_order_and_label(result: list[dict], devices) -> list[dict]:
    bt_name = None
    try:
        from audio import bluetooth
        bt_name = bluetooth.default_source_description()
    except Exception:
        pass

    virtual, hardware = [], []
    for item in result:
        raw = str(devices[item["id"]]["name"]).strip().lower()
        if raw in _LINUX_VIRTUAL:
            if raw == "default":
                item["name"] = (f"\U0001F3A7 Bluetooth: {bt_name} (system default)"
                                if bt_name else "System default (PipeWire)")
                item["default"] = True
            virtual.append(item)
        else:
            hardware.append(item)
    # 'default' first, then other virtual devices, then raw hardware.
    virtual.sort(key=lambda it: str(devices[it["id"]]["name"]).strip().lower() != "default")
    if any(v["default"] for v in virtual):
        for h in hardware:
            h["default"] = False
    return virtual + hardware


def routes_via_pipewire(device_id) -> bool:
    """True if recording from this device uses the PipeWire default source."""
    if device_id is None or device_id == "":
        return True
    try:
        return str(sd.query_devices(int(device_id))["name"]).strip().lower() in _LINUX_VIRTUAL
    except Exception:
        return False


def start(device_id: int | None = None) -> None:
    """Open an InputStream and begin recording with adaptive hardware negotiation."""
    ensure_com()
    if sys.platform.startswith("linux") and routes_via_pipewire(device_id):
        try:
            from audio import bluetooth
            bluetooth.ensure_bluetooth_mic_profile()
        except Exception:
            pass

    with _lock:
        if _state["recording"]:
            raise RuntimeError("Already recording")

        # Validate device_id
        if device_id is not None:
            try:
                device_id = int(device_id)
                if device_id < 0:
                    device_id = None
            except (ValueError, TypeError):
                device_id = None

        # Determine device capabilities
        stream = None
        used_sr = SAMPLE_RATE
        used_ch = 1
        dev_info = None

        if device_id is not None:
            try:
                dev_info = sd.query_devices(device_id)
            except Exception:
                dev_info = None
        else:
            try:
                default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
                if default_in is not None and default_in >= 0:
                    dev_info = sd.query_devices(default_in)
            except Exception:
                dev_info = None

        # Build list of configuration attempts:
        # 1. 16kHz Mono (Direct Whisper target)
        # 2. 16kHz Stereo (For stereo mic arrays accepting 16k)
        # 3. Native Sample Rate Mono
        # 4. Native Sample Rate Stereo (Realtek mic arrays on Windows WASAPI/DirectSound)
        native_sr = int(dev_info["default_samplerate"]) if dev_info else 48000
        native_ch = min(2, dev_info.get("max_input_channels", 2)) if dev_info else 2

        attempts = [
            (SAMPLE_RATE, 1),
            (SAMPLE_RATE, native_ch),
            (native_sr, 1),
            (native_sr, native_ch),
            (44100, 2),
            (48000, 2),
            (8000, 1),
        ]

        # Deduplicate attempts while preserving order
        unique_attempts = []
        for sr, ch in attempts:
            if (sr, ch) not in unique_attempts:
                unique_attempts.append((sr, ch))

        last_error = None
        recorder = None

        for sr, ch in unique_attempts:
            try:
                rec = MicRecorder(samplerate=sr, channels=ch)
                st = sd.InputStream(
                    device=device_id,
                    samplerate=sr,
                    channels=ch,
                    dtype="float32",
                    callback=_make_callback(rec),
                )
                st.start()
                stream = st
                recorder = rec
                used_sr = sr
                used_ch = ch
                break
            except Exception as err:
                last_error = err
                continue

        if stream is None or recorder is None:
            raise RuntimeError(f"Could not open microphone stream: {last_error}")

        _state["recorder"] = recorder
        _state["stream"] = stream
        _state["recording"] = True


def stop() -> str:
    """Stop recording, normalize/resample audio to 16kHz mono, and save WAV.

    Raises RuntimeError if not currently recording.
    Raises ValueError if no audio frames were captured.
    """
    with _lock:
        if not _state["recording"]:
            raise RuntimeError("Not currently recording")

        _state["recording"] = False
        recorder = _state["recorder"]
        if recorder is not None:
            recorder.active = False

        stream = _state["stream"]
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                print("Error closing mic stream:", e)
            _state["stream"] = None

    if recorder is None or not recorder.frames:
        raise ValueError("No audio was recorded.")

    # 1. Concatenate all float32 frames
    audio_data = np.concatenate(recorder.frames, axis=0)

    # 2. Downmix multi-channel / stereo array to mono (avoiding phase cancellation on Windows stereo mic arrays)
    if audio_data.ndim > 1 and audio_data.shape[1] > 1:
        mean_mix = np.mean(audio_data, axis=1)
        mean_rms = float(np.sqrt(np.mean(mean_mix ** 2)))
        ch_rms = [float(np.sqrt(np.mean(audio_data[:, c] ** 2))) for c in range(audio_data.shape[1])]
        best_ch = int(np.argmax(ch_rms))
        if ch_rms[best_ch] > 0 and mean_rms < 0.5 * ch_rms[best_ch]:
            # Channels are phase-inverted or one channel is dead; take the strongest channel
            audio_data = audio_data[:, best_ch]
        else:
            audio_data = mean_mix
    elif audio_data.ndim > 1:
        audio_data = audio_data.squeeze()

    # 3. Resample to standard 16,000 Hz if hardware ran at native rate (e.g. 48,000 or 44,100 Hz)
    capture_sr = recorder.samplerate
    if capture_sr != SAMPLE_RATE and len(audio_data) > 0:
        from math import gcd
        g = gcd(SAMPLE_RATE, capture_sr)
        audio_data = scipy.signal.resample_poly(audio_data, SAMPLE_RATE // g, capture_sr // g)

    # 4. Boost quiet microphone signals before 16-bit quantization so low-gain mics aren't lost
    peak = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0
    if 1e-5 < peak < 0.25:
        audio_data = audio_data * (0.5 / peak)

    # 5. Clip and convert to 16-bit PCM integer WAV
    audio_clipped = np.clip(audio_data, -1.0, 1.0)
    audio_int16 = (audio_clipped * 32767.0).astype(np.int16)

    wav.write(MIC_WAV_PATH, SAMPLE_RATE, audio_int16)
    return MIC_WAV_PATH
