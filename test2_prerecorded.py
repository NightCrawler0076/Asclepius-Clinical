"""
Transcribe an existing audio file using OpenAI Whisper.

Whisper uses ffmpeg internally to decode the file, so it accepts pretty
much any audio/video format and sample rate (mp3, wav, m4a, mp4, etc.) —
no manual resampling or channel conversion needed.

DEPENDENCIES:
    pip install openai-whisper

    ffmpeg must also be installed on your system:
        Windows: choco install ffmpeg   (or download from ffmpeg.org and add to PATH)
        Mac:     brew install ffmpeg
        Linux:   sudo apt install ffmpeg

USAGE:
    python transcribe_file.py path/to/audio.wav
    python transcribe_file.py path/to/audio.mp3 --model small
"""

import argparse
import os
import whisper


def transcribe(filepath, model_size="base"):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No such file: {filepath}")

    print(f"Loading Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)

    print(f"Transcribing {filepath} ...")
    result = model.transcribe(filepath)
    return result["text"]


def main():
    parser = argparse.ArgumentParser(description="Transcribe an audio file with Whisper.")
    parser.add_argument("filepath", help="Path to the audio file to transcribe")
    parser.add_argument(
        "--model", default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Bigger = more accurate, slower."
    )
    parser.add_argument(
        "--output", default=None,
        help="Path to save the transcript .txt file (default: <input filename>.txt)"
    )
    args = parser.parse_args()

    text = transcribe(args.filepath, args.model)

    output_path = args.output or (os.path.splitext(args.filepath)[0] + ".txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text.strip())

    print(f"\nTranscription saved to {output_path}")
    print("\n--- Transcript ---")
    print(text)


if __name__ == "__main__":
    main()