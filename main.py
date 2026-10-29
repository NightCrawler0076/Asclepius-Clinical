"""
Whisper backend for the Flutter web frontend.

Wraps the same transcription logic as test2_prerecorded.py behind an HTTP
API, with CORS enabled so a browser tab (Flutter web, served from
localhost:xxxxx) is allowed to call it.

Only /transcribe/file is implemented — that's all the browser build needs,
since:
  - Live Microphone: browser records audio itself, then uploads it here,
    same endpoint as the file-picker mode.
  - System / Device Audio: disabled in the web frontend. Browsers can't do
    OS-level loopback capture (see test3_ondevice.py) — that only makes
    sense as a future desktop build, not this one.

DEPENDENCIES:
    pip install fastapi uvicorn python-multipart openai-whisper

    ffmpeg must also be installed on your system:
        Windows: choco install ffmpeg   (or download from ffmpeg.org and add to PATH)
        Mac:     brew install ffmpeg
        Linux:   sudo apt install ffmpeg

RUN:
    uvicorn main:app --reload --port 8000

Then point the Flutter app's ApiService.baseUrl at http://localhost:8000
"""

import os
import tempfile

import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

MODEL_SIZE = "base"  # tiny/base/small/medium/large — bigger = more accurate, slower

app = FastAPI(title="Whisper Transcriber Backend")

# The Flutter web build runs on its own localhost port (whatever `flutter
# run -d chrome` picks) which counts as a different origin from this
# server's port 8000 — so CORS has to be opened up explicitly, or the
# browser will block every request before it even reaches these endpoints.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local dev; lock this down before deploying anywhere public
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load once at startup so each request doesn't reload the model from disk.
print(f"Loading Whisper model '{MODEL_SIZE}'...")
model = whisper.load_model(MODEL_SIZE)
print("Model loaded. Ready for requests.")


@app.post("/transcribe/file")
async def transcribe_file(audio: UploadFile = File(...)):
    """
    Accepts an uploaded audio file (mic recording or a picked file from
    the Flutter app) and returns its transcript as JSON: {"text": "..."}
    """
    suffix = os.path.splitext(audio.filename or "")[1] or ".wav"

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        result = model.transcribe(tmp_path)
        return {"text": result["text"].strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_SIZE}
