"""
Speech-to-Text recorder (Microphone / Earbuds mic)

Records audio from your default microphone until you press Ctrl+C,
then transcribes it using OpenAI Whisper and saves the result to a .txt file.

DEPENDENCIES:
    pip install openai-whisper sounddevice numpy scipy

    Whisper also needs ffmpeg installed on your system:
        Windows: choco install ffmpeg   (or download from ffmpeg.org and add to PATH)
        Mac:     brew install ffmpeg
        Linux:   sudo apt install ffmpeg

USAGE:
    python mic_transcribe.py
    (speak into your earbuds mic, then press Ctrl+C to stop and transcribe)
"""

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import whisper

SAMPLE_RATE = 16000   # Whisper is trained on 16kHz audio
CHANNELS = 1
WAV_FILENAME = "recording_mic.wav"
TXT_FILENAME = "transcription_mic.txt"
MODEL_SIZE = "base"   # tiny/base/small/medium/large — bigger = more accurate, slower

frames = []


def callback(indata, frame_count, time_info, status):
    if status:
        print(status)
    frames.append(indata.copy())


def record_until_interrupt():
    print("Recording from microphone... Press Ctrl+C to stop.")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                         dtype="int16", callback=callback):
        try:
            while True:
                sd.sleep(1000)
        except KeyboardInterrupt:
            print("\nRecording stopped.")


def save_wav(filename):
    if not frames:
        raise RuntimeError("No audio was recorded.")
    audio = np.concatenate(frames, axis=0)
    wav.write(filename, SAMPLE_RATE, audio)
    print(f"Saved audio to {filename}")


def transcribe(filename, model_size=MODEL_SIZE):
    print(f"Loading Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)
    print("Transcribing...")
    result = model.transcribe(filename)
    return result["text"]


def main():
    record_until_interrupt()
    save_wav(WAV_FILENAME)
    text = transcribe(WAV_FILENAME)

    with open(TXT_FILENAME, "w", encoding="utf-8") as f:
        f.write(text.strip())

    print(f"\nTranscription saved to {TXT_FILENAME}")
    print("\n--- Transcript ---")
    print(text)


if __name__ == "__main__":
    main()