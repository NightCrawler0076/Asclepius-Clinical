#!/usr/bin/env bash
# One-shot setup for Raspberry Pi 5 (64-bit Raspberry Pi OS Bookworm / Trixie).
# Works from wherever the folder was copied to, for whatever user runs it.
#
# Usage (from the project root):
#   bash deploy/pi/setup_pi.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_USER="$(id -un)"
cd "$PROJECT_DIR"
echo "==> Project dir: $PROJECT_DIR (user: $RUN_USER)"

# Fix line endings and permissions if copied from Windows
for f in run.sh deploy/pi/*.sh; do
  [ -f "$f" ] && sed -i 's/\r$//' "$f"
done
chmod +x run.sh deploy/pi/*.sh 2>/dev/null || true

# Remove any Windows-built caches / venvs that may have been copied across
find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache
if [ -d venv ] && [ ! -x venv/bin/python ]; then
  echo "==> Removing Windows virtualenv (venv/Scripts) copied from PC"
  rm -rf venv
fi

if [ "$(uname -m)" != "aarch64" ]; then
  echo "WARNING: expected aarch64 (64-bit OS). Detected $(uname -m)."
  echo "         32-bit Raspberry Pi OS is not supported by faster-whisper wheels."
fi

MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
echo "==> RAM: ${MEM_MB} MB"

echo "==> Installing system packages (apt)"
sudo apt-get update || true
sudo apt-get install -y \
  python3-venv python3-dev build-essential cmake pkg-config git wget \
  libportaudio2 portaudio19-dev libopenblas-dev \
  ffmpeg alsa-utils || true

echo "==> Installing Bluetooth audio stack (PipeWire + BlueZ) for earbud mics"
sudo apt-get install -y \
  bluez pipewire pipewire-pulse pipewire-alsa wireplumber \
  libspa-0.2-bluetooth pulseaudio-utils || true
sudo rfkill unblock bluetooth 2>/dev/null || true
sudo systemctl enable --now bluetooth 2>/dev/null || true

# Server-side mic recording needs the audio group; bluetoothctl needs bluetooth.
for grp in audio bluetooth; do
  if ! id -nG "$RUN_USER" | grep -qw "$grp"; then
    sudo usermod -aG "$grp" "$RUN_USER" 2>/dev/null || true
    echo "    Added $RUN_USER to '$grp' group (log out/in or reboot to apply)."
  fi
done

# Keep the user's PipeWire session running at boot without a login
sudo loginctl enable-linger "$RUN_USER" 2>/dev/null || true
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user enable --now pipewire pipewire-pulse wireplumber 2>/dev/null \
  || echo "    (PipeWire user services will start after login/reboot)"

echo "==> Creating virtualenv"
[ -d venv ] || python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip wheel setuptools

if python -c "import llama_cpp" 2>/dev/null; then
  echo "==> llama-cpp-python already installed, skipping build"
else
  echo "==> Building llama-cpp-python with OpenBLAS + ARM NEON..."
  CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DGGML_NATIVE=ON" \
    pip install --no-cache-dir llama-cpp-python || true
fi

echo "==> Installing Python requirements"
pip install -r requirements-pi.txt
pip install pytest || true

echo "==> Checking models (reusing local models if already in models/ folder)"
mkdir -p models/whisper

# Clean up deprecated TinyLlama model if present
rm -f models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf 2>/dev/null || true

# Check LLM model
if [ -f models/qwen2.5-1.5b-instruct-q4_k_m.gguf ]; then
  echo "    ✓ Qwen2.5 1.5B model already present in models/ (skipping download)."
elif [ -f models/llama-3.2-1b-medical-q4_km.gguf ] || [ -f models/Llama3.2-1B-Medical-Q4_KM.gguf ]; then
  echo "    ✓ Llama 3.2 1B Medical model already present in models/ (skipping download)."
elif [ -f models/qwen2.5-3b-medical-instruct-q4_k_m.gguf ]; then
  echo "    ✓ Qwen2.5 3B Medical model already present in models/ (skipping download)."
else
  echo "    Downloading Qwen2.5 1.5B (~1.1 GB)..."
  wget -O models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf" || true
fi

# Check Whisper models
found_any_whisper=0
for size in small base medium; do
  if [ -f "models/whisper/faster-whisper-$size/model.bin" ] || [ -f "models/whisper/$size/model.bin" ]; then
    echo "    ✓ Whisper '$size' model already present in models/whisper/ (skipping download)."
    found_any_whisper=1
  fi
done

if [ "$found_any_whisper" = "0" ]; then
  echo "    No local Whisper model found in models/whisper/. Downloading default Whisper small..."
  python - <<'PY' || true
from faster_whisper import WhisperModel
WhisperModel("small", device="cpu", compute_type="int8", download_root="models/whisper")
print("Whisper small downloaded to models/whisper.")
PY
fi

echo "==> Microphones detected:"
arecord -l || true

echo
echo "Done. Start the app with:  ./run.sh"
echo "Then open http://$(hostname -I 2>/dev/null | awk '{print $1}'):5000 from any device on your network."
echo "If using Bluetooth earbuds, pair them via the Pi's desktop Bluetooth menu."
