"""
Audio preprocessing — DC removal, bandpass filtering, and RMS normalization.

Improves Whisper ASR accuracy by:
1. Removing DC offset (mic bias that shifts the waveform)
2. Bandpass filtering (100 Hz – 8 kHz) — eliminates AC hum (50/60 Hz),
   sub-bass rumble, and ultrasonic noise while keeping all speech frequencies
3. RMS normalization — ensures consistent loudness regardless of mic gain,
   which reduces Whisper's VAD false-negatives on quiet recordings

Uses only scipy and numpy (already available as transitive whisper dependencies).
Falls back to the original file gracefully on any error.
"""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Target RMS level (0.0–1.0 range, -18 dBFS is a good clinical target)
_TARGET_RMS = 0.08
_LOW_CUT_HZ  = 100     # Hz — removes AC hum, sub-bass rumble
_HIGH_CUT_HZ = 8000    # Hz — keeps all speech frequencies, cuts ultrasonic noise
_FILTER_ORDER = 5


def _bandpass_coeffs(low_hz: float, high_hz: float, sample_rate: int):
    """Return scipy Butterworth bandpass filter coefficients (sos form)."""
    from scipy.signal import butter
    nyq = sample_rate / 2.0
    low  = low_hz  / nyq
    high = min(high_hz / nyq, 0.999)  # must be < 1.0 (Nyquist)
    return butter(_FILTER_ORDER, [low, high], btype="band", output="sos")


def preprocess(wav_path: str) -> str:
    """Apply preprocessing pipeline to a WAV file.

    Steps:
      1. DC offset removal
      2. Bandpass filter (100 Hz – 8 kHz)
      3. RMS loudness normalization

    Returns the path to the preprocessed WAV file.
    On any error, returns the original wav_path unchanged.
    """
    try:
        import numpy as np
        from scipy.io import wavfile
        from scipy.signal import sosfilt

        sample_rate, data = wavfile.read(wav_path)

        # Convert to float64 in [-1.0, 1.0]
        if data.dtype == np.int16:
            audio = data.astype(np.float64) / 32768.0
        elif data.dtype == np.int32:
            audio = data.astype(np.float64) / 2147483648.0
        elif data.dtype == np.float32:
            audio = data.astype(np.float64)
        else:
            audio = data.astype(np.float64)

        # Handle stereo — mix down to mono
        if audio.ndim == 2:
            audio = audio.mean(axis=1)

        # 1. DC offset removal
        audio -= audio.mean()

        # 2. Bandpass filter (only if sample rate allows)
        high_cut = min(_HIGH_CUT_HZ, sample_rate // 2 - 1)
        if _LOW_CUT_HZ < high_cut:
            sos = _bandpass_coeffs(_LOW_CUT_HZ, high_cut, sample_rate)
            audio = sosfilt(sos, audio)

        # 3. RMS normalization
        rms = np.sqrt(np.mean(audio ** 2))
        if rms > 1e-6:                  # avoid division by silence
            audio = audio * (_TARGET_RMS / rms)
            audio = np.clip(audio, -1.0, 1.0)  # prevent clipping artifacts

        # Write preprocessed audio to a temp file
        out_int16 = (audio * 32767).astype(np.int16)
        fd, out_path = tempfile.mkstemp(suffix="_preprocessed.wav")
        os.close(fd)
        wavfile.write(out_path, sample_rate, out_int16)

        logger.debug("Audio preprocessed: %.2fs, RMS %.4f → %.4f, path=%s",
                     len(audio) / sample_rate, rms, _TARGET_RMS, out_path)
        return out_path

    except Exception as exc:
        logger.warning("Audio preprocessing failed (%s) — using original file.", exc)
        return wav_path

