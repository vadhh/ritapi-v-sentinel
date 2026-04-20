#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USB_DIR="$SCRIPT_DIR"
COMPOSE_FILE="$USB_DIR/docker/docker-compose.usb.yml"

echo ">>> Stopping V-Sentinel demo stack..."
docker compose -f "$COMPOSE_FILE" --project-directory "$USB_DIR" down
echo ">>> Done."
