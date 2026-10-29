#!/usr/bin/env bash
# Bluetooth Earbud/Headset Mic Management for Raspberry Pi
# Usage:
#   bash deploy/pi/bt_mic.sh connect [MAC_ADDRESS]   # Reconnect earbuds and set as default mic
#   bash deploy/pi/bt_mic.sh disconnect              # Disconnect
#   bash deploy/pi/bt_mic.sh status                  # Check connection and audio profile
#   bash deploy/pi/bt_mic.sh forget                  # Unpair earbuds

set -euo pipefail

CONFIG_DIR="${HOME}/.config/emb"
MAC_FILE="${CONFIG_DIR}/bt_device"
mkdir -p "$CONFIG_DIR"

cmd="${1:-status}"
target_mac="${2:-}"

get_mac() {
  if [ -n "$target_mac" ]; then
    echo "$target_mac"
    return
  fi
  if [ -f "$MAC_FILE" ]; then
    cat "$MAC_FILE"
    return
  fi
  # Find first paired audio device from bluetoothctl
  local paired
  paired=$(bluetoothctl devices | head -n 1 | awk '{print $2}')
  if [ -n "$paired" ]; then
    echo "$paired"
    return
  fi
  echo ""
}

case "$cmd" in
  connect)
    MAC=$(get_mac)
    if [ -z "$MAC" ]; then
      echo "No saved or paired Bluetooth device found."
      echo "Pair your earbuds first using Raspberry Pi desktop Bluetooth menu or: bluetoothctl scan on"
      exit 0
    fi
    echo "Connecting to Bluetooth headset ($MAC)..."
    bluetoothctl connect "$MAC" || true
    echo "$MAC" > "$MAC_FILE"
    
    # Give BlueZ and PipeWire a second to negotiate audio profile
    sleep 2
    
    # Ensure profile is Headset / HFP (required for microphone input)
    if command -v pactl >/dev/null 2>&1; then
      CARD=$(pactl list cards short 2>/dev/null | grep -i "bluez" | head -n 1 | awk '{print $2}')
      if [ -n "$CARD" ]; then
        pactl set-card-profile "$CARD" headset-head-unit 2>/dev/null || true
      fi
      
      # Set Bluetooth input as default PipeWire source
      BT_SOURCE=$(pactl list sources short 2>/dev/null | grep -i "bluez" | head -n 1 | awk '{print $2}')
      if [ -n "$BT_SOURCE" ]; then
        pactl set-default-source "$BT_SOURCE"
        echo "Set default recording source to: $BT_SOURCE"
      fi
    fi
    echo "Bluetooth mic connected."
    ;;

  disconnect)
    MAC=$(get_mac)
    if [ -n "$MAC" ]; then
      bluetoothctl disconnect "$MAC" || true
      echo "Disconnected $MAC."
    fi
    ;;

  status)
    echo "==> Bluetooth Controller:"
    bluetoothctl show | grep -E "Powered|Name|Alias" || true
    echo "==> Connected Devices:"
    bluetoothctl devices Connected || true
    echo "==> PipeWire Audio Sources:"
    if command -v wpctl >/dev/null 2>&1; then
      wpctl status | grep -A 8 "Sources:" || true
    elif command -v pactl >/dev/null 2>&1; then
      pactl list sources short || true
    fi
    ;;

  forget)
    MAC=$(get_mac)
    if [ -n "$MAC" ]; then
      bluetoothctl remove "$MAC" || true
      rm -f "$MAC_FILE"
      echo "Unpaired $MAC."
    fi
    ;;

  *)
    echo "Usage: $0 {connect|disconnect|status|forget} [MAC_ADDRESS]"
    exit 1
    ;;
esac
