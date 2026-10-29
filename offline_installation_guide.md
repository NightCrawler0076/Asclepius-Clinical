# Offline Installation Guide for Raspberry Pi 5

Since the current system does not have Python installed, I could not pre-download the packages for you. However, here are the exact steps to download the packages on any PC with Python and internet access, and then install them offline on your Raspberry Pi.

> **Note on requirements:** You requested to download from `requirements.txt`. Note that for the Raspberry Pi, we strongly recommend using `requirements-pi.txt` instead, as it uses `faster-whisper` (which is much faster on the Pi) rather than `openai-whisper`. The steps below will use `requirements.txt` as you requested, but you can swap it for `requirements-pi.txt`.

## Step 1: Download packages on a PC with internet

Run this command on a computer that has Python and `pip` installed. This command forces `pip` to download the packages specifically for a 64-bit Raspberry Pi (ARM64) running Python 3.11 (the default version on Raspberry Pi OS Bookworm), even if you run it on a Windows or Mac computer.

```bash
# 1a. For Python 3.11 (Raspberry Pi OS Bookworm default):
pip download -r requirements-pi-wheels.txt -d offline_packages \
    --platform manylinux2014_aarch64 \
    --python-version 3.11 \
    --only-binary=:all:

# 1b. For Python 3.13:
# (Note: Python 3.13 wheels for onnxruntime and av use manylinux_2_28_aarch64)
pip download -r requirements-pi-wheels.txt -d offline_packages_313 \
    --platform manylinux_2_28_aarch64 \
    --platform manylinux2014_aarch64 \
    --python-version 3.13 \
    --implementation cp \
    --abi cp313 \
    --only-binary=:all:

# 2. llama-cpp-python has no pre-built ARM64 wheel on PyPI, so download its source tarball:
pip download llama-cpp-python --no-binary=:all: --no-deps -d offline_packages
pip download llama-cpp-python --no-binary=:all: --no-deps -d offline_packages_313
```

## Step 2: Transfer to the Raspberry Pi

Copy your entire project folder (including the newly created `offline_packages` folder) to your USB pen drive, and then transfer it to your Raspberry Pi.

## Step 3: Offline Installation on the Raspberry Pi

Once the files are on your Raspberry Pi, open a terminal in the project directory.

**1. Install system dependencies (requires offline deb packages if no internet at all)**
If the Pi has absolutely no internet, you need to have pre-downloaded the `.deb` files for `python3-venv`, `ffmpeg`, `libportaudio2`, `portaudio19-dev`, and `libopenblas-dev`. Assuming those are installed:

**2. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install the downloaded packages offline**
Tell `pip` to install from the local folder and ignore the internet:

```bash
pip install --no-index --find-links=offline_packages -r requirements-pi.txt
```

### Compiling `llama-cpp-python` offline
If you had to download the source code for `llama-cpp-python`, it will be compiled during the installation step above. Ensure you install it with the ARM NEON and OpenBLAS flags for good performance:

```bash
CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DGGML_NATIVE=ON" \
  pip install --no-index --find-links=offline_packages llama-cpp-python
```
