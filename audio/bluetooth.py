"""
Bluetooth Audio helper for Linux / Raspberry Pi (BlueZ + PipeWire / PulseAudio).
Detects connected Bluetooth audio headsets and exposes helper functions
for querying active devices and status.
"""

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def default_source_description() -> str | None:
    """Return a human-readable name of the current Bluetooth audio source, if connected.

    Queries PipeWire (pactl / wpctl) or BlueZ (bluetoothctl) to see if a Bluetooth
    headset is active/connected as an input source. Returns None if no Bluetooth
    mic is active or if detection fails.
    """
    try:
        # 1. Try pactl to inspect the default source name and description
        if shutil.which("pactl"):
            res = subprocess.run(
                ["pactl", "get-default-source"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            default_source = res.stdout.strip() if res.returncode == 0 else ""

            if "bluez" in default_source.lower():
                desc_res = subprocess.run(
                    ["pactl", "list", "sources"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if desc_res.returncode == 0:
                    lines = desc_res.stdout.splitlines()
                    in_target = False
                    for line in lines:
                        if default_source in line:
                            in_target = True
                        elif in_target and line.strip().startswith("Name:"):
                            in_target = False
                        elif in_target and "Description:" in line:
                            return line.split("Description:", 1)[1].strip()

        # 2. Try wpctl status if pactl didn't return a name
        if shutil.which("wpctl"):
            res = subprocess.run(
                ["wpctl", "status"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                in_sources = False
                for line in res.stdout.splitlines():
                    if "Audio" in line and "Sources:" in line:
                        in_sources = True
                        continue
                    if in_sources and ("Filters:" in line or "Streams:" in line or "Sinks:" in line):
                        break
                    if in_sources and "*" in line and ("bluez" in line.lower() or "headset" in line.lower() or "earbuds" in line.lower()):
                        clean = line.replace("│", "").replace("*", "").strip()
                        if "." in clean:
                            clean = clean.split(".", 1)[1].strip()
                        if "[" in clean:
                            clean = clean.split("[", 1)[0].strip()
                        if clean:
                            return clean

        # 3. Fallback: check bluetoothctl for connected audio devices
        if shutil.which("bluetoothctl"):
            res = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                first_line = res.stdout.strip().splitlines()[0]
                parts = first_line.split(" ", 2)
                if len(parts) >= 3:
                    return parts[2].strip()

    except Exception as e:
        logger.debug("Failed to detect Bluetooth audio source: %s", e)

    return None


def ensure_bluetooth_mic_profile() -> None:
    """On Linux/Raspberry Pi, automatically switch connected Bluetooth headsets
    from A2DP (playback-only) to HSP/HFP (headset-head-unit) so the microphone
    is active, and set the bluez input source as the PipeWire/PulseAudio default.
    """
    if not shutil.which("pactl"):
        return

    try:
        # 1. Check if a bluez_input source already exists
        sources_res = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        bluez_source = None
        if sources_res.returncode == 0:
            for line in sources_res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and "bluez_input" in parts[1].lower():
                    bluez_source = parts[1]
                    break

        # 2. If no bluez_input exists yet, switch bluez_card from A2DP to HSP/HFP
        if not bluez_source:
            cards_res = subprocess.run(
                ["pactl", "list", "short", "cards"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if cards_res.returncode == 0:
                for line in cards_res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and "bluez_card" in parts[1].lower():
                        card_name = parts[1]
                        for profile in (
                            "headset-head-unit",
                            "headset-head-unit-msbc",
                            "headset-head-unit-cvsd",
                        ):
                            prof_res = subprocess.run(
                                ["pactl", "set-card-profile", card_name, profile],
                                capture_output=True,
                                text=True,
                                timeout=2,
                            )
                            if prof_res.returncode == 0:
                                break

            # Re-query sources after switching profile
            sources_res = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if sources_res.returncode == 0:
                for line in sources_res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and "bluez_input" in parts[1].lower():
                        bluez_source = parts[1]
                        break

        # 3. Set bluez_input as default source and ensure it is unmuted
        if bluez_source:
            subprocess.run(
                ["pactl", "set-default-source", bluez_source],
                capture_output=True,
                timeout=2,
            )
            subprocess.run(
                ["pactl", "set-source-mute", bluez_source, "0"],
                capture_output=True,
                timeout=2,
            )
    except Exception as e:
        logger.debug("Could not auto-configure Bluetooth mic profile: %s", e)

