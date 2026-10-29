"""
Speech-to-Text recorder (SYSTEM AUDIO / "What You Hear" — e.g. a YouTube video playing)

Records whatever audio is playing OUT of your PC's speakers/headphones
(loopback), instead of recording from a microphone, until you press Ctrl+C,
then transcribes it using OpenAI Whisper and saves the result to a .txt file.

WHY THIS IS DIFFERENT FROM A MIC SCRIPT:
    Your OS doesn't let a normal program "listen" to the output device
    directly — you have to record from a special LOOPBACK / MONITOR source
    that mirrors whatever is being played.

    - Windows: WASAPI has a native loopback mode. No extra software needed.
               Handled automatically by the `soundcard` library below.
    - macOS:   No native loopback. Install a free virtual audio driver
               called BlackHole first:
                   brew install blackhole-2ch
               Then set your system Output (or a Multi-Output Device in
               Audio MIDI Setup) to include BlackHole, so audio is routed
               through it. This script will then pick up "BlackHole 2ch"
               as a recordable device.
    - Linux:   PulseAudio/PipeWire automatically create a ".monitor" source
               for every output/sink. This script auto-detects it.

DEPENDENCIES:
    pip install openai-whisper soundcard numpy scipy

    Whisper also needs ffmpeg installed on your system:
        Windows: choco install ffmpeg   (or download from ffmpeg.org and add to PATH)
        Mac:     brew install ffmpeg
        Linux:   sudo apt install ffmpeg

USAGE:
    python system_audio_transcribe.py
    (play the YouTube video / audio, then press Ctrl+C to stop and transcribe)

    To record from a specific device instead of the default output, run:
    python system_audio_transcribe.py --list         # see available devices
    python system_audio_transcribe.py --device "Speakers"
"""

import argparse
import sys

import numpy as np
import scipy.io.wavfile as wav
import soundcard as sc
import whisper

SAMPLE_RATE = 16000   # Whisper is trained on 16kHz audio
WAV_FILENAME = "recording_system_audio.wav"
TXT_FILENAME = "transcription_system_audio.txt"
MODEL_SIZE = "base"   # tiny/base/small/medium/large — bigger = more accurate, slower
BLOCK_SIZE = 1024

frames = []


def list_devices():
    print("\nAvailable speakers/output devices (use one of these names with --device):\n")
    for spk in sc.all_speakers():
        default_tag = "  [DEFAULT]" if spk.id == sc.default_speaker().id else ""
        print(f"  - {spk.name}{default_tag}")
    print()


def get_loopback_mic(device_name=None):
    """
    Returns a soundcard Microphone object that captures the OUTPUT
    (loopback) of a speaker device, instead of an actual microphone.
    """
    if device_name:
        speaker = sc.get_speaker(device_name)
    else:
        speaker = sc.default_speaker()

    # On Windows/Linux, soundcard exposes a loopback-capable "microphone"
    # that matches the speaker's id/name.
    try:
        loopback_mic = sc.get_microphone(id=speaker.id, include_loopback=True)
    except Exception:
        loopback_mic = sc.get_microphone(speaker.name, include_loopback=True)

    print(f"Capturing system audio from: {speaker.name}")
    return loopback_mic


def record_until_interrupt(device_name=None):
    mic = get_loopback_mic(device_name)
    print("Recording system audio... Press Ctrl+C to stop.")

    try:
        with mic.recorder(samplerate=SAMPLE_RATE, channels=1) as recorder:
            while True:
                data = recorder.record(numframes=BLOCK_SIZE)  # float32, shape (N, 1)
                frames.append(data.copy())
    except KeyboardInterrupt:
        print("\nRecording stopped.")


def save_wav(filename):
    if not frames:
        raise RuntimeError(
            "No audio was recorded. Make sure something was actually playing, "
            "and that the correct output device was selected (see --list)."
        )
    audio = np.concatenate(frames, axis=0)
    # soundcard gives float32 in [-1, 1]; convert to int16 PCM for a standard wav file
    audio_int16 = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio_int16 * 32767).astype(np.int16)
    wav.write(filename, SAMPLE_RATE, audio_int16)
    print(f"Saved audio to {filename}")


def transcribe(filename, model_size=MODEL_SIZE):
    print(f"Loading Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)
    print("Transcribing...")
    result = model.transcribe(filename)
    return result["text"]


def main():
    parser = argparse.ArgumentParser(description="Transcribe system/output audio.")
    parser.add_argument("--list", action="store_true", help="List available output devices and exit.")
    parser.add_argument("--device", type=str, default=None,
                         help="Name (or partial name) of the output device to capture from.")
    args = parser.parse_args()

    if args.list:
        list_devices()
        sys.exit(0)

    record_until_interrupt(args.device)
    save_wav(WAV_FILENAME)
    text = transcribe(WAV_FILENAME)

    with open(TXT_FILENAME, "w", encoding="utf-8") as f:
        f.write(text.strip())

    print(f"\nTranscription saved to {TXT_FILENAME}")
    print("\n--- Transcript ---")
    print(text)


if __name__ == "__main__":
    main()