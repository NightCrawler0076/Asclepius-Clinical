# Running on Raspberry Pi 5

## Hardware
- **Raspberry Pi 5, 8 GB** recommended (4 GB works with `tiny`/`base` + Qwen 0.5B)
- Active cooler (sustained inference will thermal-throttle without it)
- Official 27 W USB-C PSU
- USB microphone (the Pi has no analog mic input)
- NVMe SSD via M.2 HAT (optional, but much faster model loading than microSD)

## 1. Flash the OS
Use **Raspberry Pi Imager** → *Raspberry Pi OS (64-bit)* Bookworm.
In the advanced settings, enable SSH, set username/password and Wi-Fi.

> 32-bit OS will **not** work (no faster-whisper / CTranslate2 wheels).

## 2. Copy the project
Copy the whole folder anywhere on the Pi (USB stick, SMB share, or scp).
The `models/*.gguf` files (~1.1 GB) come along, so no LLM download is needed.
```powershell
scp -r d:\Emb_2 <user>@<pi-ip>:~/Emb_2
```
Do **not** copy a Windows `venv/` folder — setup builds a fresh one (and
deletes a Windows one if it finds it).

## 3. Run setup
```bash
cd ~/Emb_2
bash deploy/pi/setup_pi.sh
```
This fixes line endings / permissions, installs system packages (ffmpeg,
PortAudio, OpenBLAS), builds `llama-cpp-python` with ARM optimizations,
installs `requirements-pi.txt`, and checks models.
Pre-downloaded models in `models/` are used directly; missing models are downloaded automatically.

## 4. Test & run
```bash
arecord -l                                   # confirm USB mic is listed
arecord -d 3 -f S16_LE -r 16000 test.wav && aplay test.wav
./run.sh
```
Open `http://<pi-ip>:5000` from a laptop/phone on the same network.

## Configuration (env vars)
On a Pi these defaults are applied automatically (detected via `/proc/device-tree/model`).

| Variable | Pi default | Purpose |
|---|---|---|
| `EMB_WHISPER_MODEL` | `base` | `tiny` / `base` / `small` |
| `EMB_ASR_BACKEND` | `auto` → faster-whisper | or `openai-whisper` |
| `EMB_ASR_COMPUTE_TYPE` | `int8` | faster-whisper quantization |
| `EMB_ASR_BEAM_SIZE` | `1` | higher = slower, slightly more accurate |
| `EMB_LLM_MODEL` | `qwen2.5-1.5b` | `qwen2.5-1.5b`, `llama-3.2-1b-medical`, `tinyllama-1.1b` |
| `EMB_LLM_THREADS` | `4` | CPU threads for LLM + ASR |
| `EMB_ENABLE_SYSTEM_AUDIO` | `0` | loopback capture (needs `soundcard` + PipeWire) |
| `EMB_FORCE_PI` | auto | force Pi profile on another machine for testing |

## Expected performance (Pi 5, 8 GB, rough)
| Step | Time |
|---|---|
| Whisper `base` int8, 60 s audio | ~10–20 s |
| Whisper `small` int8, 60 s audio | ~30–60 s |
| Qwen 2.5 1.5B refinement | ~10–25 s |
| Llama 3.2 1B Medical refinement | ~8–20 s |
| TinyLlama 1.1B refinement | ~15–40 s |

First request after boot is slower (model load).

## Troubleshooting
- **`OSError: PortAudio library not found`** → `sudo apt install libportaudio2`
- **No input devices** → check `arecord -l`; add user to `audio` group: `sudo usermod -aG audio $USER`
- **Killed / OOM** → use `tiny` or `base`, `qwen2.5-0.5b`, and add swap:
  `sudo dphys-swapfile swapoff && sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile && sudo dphys-swapfile setup && sudo dphys-swapfile swapon`
- **Throttling** → `vcgencmd measure_temp` / `vcgencmd get_throttled`; fit the active cooler
- **`bash\r: No such file`** → CRLF line endings: `sed -i 's/\r$//' deploy/pi/*.sh`
