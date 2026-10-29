ramees is gay
# Whisper Transcriber — Flask

Same three modes as the original Streamlit app, plus system/device audio
capture, as one Flask app you run with a single command.

| Tab | Mirrors | What it does |
|---|---|---|
| 🎤 Microphone | Streamlit app's mic tab / `test.py` | Server records from a chosen input device until you click Stop |
| 🔊 System / Device Audio | `test3_ondevice.py` | Server captures loopback audio (whatever's playing out of your speakers) until you click Stop |
| 📁 Upload File | Streamlit app's upload tab / `test2_prerecorded.py` | Pick an existing audio/video file to transcribe |

## Why Flask instead of Streamlit

Streamlit reruns your whole script top-to-bottom on every interaction and
manages UI state through `st.session_state`. Flask is just a small HTTP
server: the page is static HTML/JS, and each button click calls a specific
API endpoint (`/api/mic/start`, `/api/mic/stop`, etc.) that does one job and
returns JSON. Recording state (the active stream, captured frames) now
lives in a couple of global dicts on the server instead of session state,
since this app is meant for one person running it locally — same
assumption the Streamlit version made.

## Raspberry Pi 5 quickstart

Copy this folder to the Pi (64-bit Raspberry Pi OS), then:
```bash
cd ~/Emb_2
bash deploy/pi/setup_pi.sh     # one-shot setup (creates venv, builds ARM acceleration)
./run.sh
```
Full guide: [deploy/pi/README.md](deploy/pi/README.md)

## Setup

```bash
pip install -r requirements.txt
```

ffmpeg is still required (Whisper decodes through it):
```
Windows: choco install ffmpeg
Mac:     brew install ffmpeg
Linux:   sudo apt install ffmpeg
```

On Mac, system audio capture additionally needs a virtual audio driver,
same as `test3_ondevice.py`:
```
brew install blackhole-2ch
```
then set your Mac's Output (or a Multi-Output Device) to include
BlackHole so audio actually routes through it.

## Run

```bash
python app.py
```

Then open **http://localhost:5000** — one process, one command.

## Notes

- The Whisper model is loaded once per size and cached in memory (mirrors
  Streamlit's `@st.cache_resource`) — the first transcription with a given
  model size will be slower while it loads.
- Recorded/captured audio is saved to your OS temp folder
  (`recording_mic.wav`, `recording_system_audio.wav`) and played back
  in-page via an `<audio>` tag, same as Streamlit's `st.audio`.
- This app assumes a single local user, like the original — it doesn't
  handle multiple concurrent recordings from different browser tabs.
