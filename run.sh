#!/usr/bin/env bash
# Start the app on the Raspberry Pi. Run deploy/pi/setup_pi.sh once first.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -x venv/bin/python ]; then
  echo "venv not found. Run first:  bash deploy/pi/setup_pi.sh"
  exit 1
fi

export PYTHONUNBUFFERED=1
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$IP" ]; then
  echo "Open http://${IP}:5000 from any device on your local network."
else
  echo "Offline / Standalone mode: Open http://localhost:5000 on the Raspberry Pi browser."
fi
exec venv/bin/python app.py "$@"
