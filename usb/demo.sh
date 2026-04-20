#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USB_DIR="$SCRIPT_DIR"

COMPOSE_FILE="$USB_DIR/docker/docker-compose.usb.yml"
IMAGE_TAR="$USB_DIR/images/vsentinel.tar"

DJANGO_IMAGE="ritapi-v-sentinel/django:usb"
MINIFW_IMAGE="ritapi-v-sentinel/minifw:usb"
POSTGRES_IMAGE="postgres:16-alpine"
REDIS_IMAGE="redis:7-alpine"

die() { echo "ERROR: $*" >&2; exit 1; }

# ── 0. Docker daemon check ─────────────────────────────────────────────────
docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop (or the Docker daemon) and try again."

# ── 1. Load images if any are missing ─────────────────────────────────────
needs_load=0
for img in "$DJANGO_IMAGE" "$MINIFW_IMAGE" "$POSTGRES_IMAGE" "$REDIS_IMAGE"; do
    docker image inspect "$img" >/dev/null 2>&1 || { needs_load=1; break; }
done

if [[ $needs_load -eq 1 ]]; then
    echo ">>> Loading images from $(basename "$IMAGE_TAR") (this may take a few minutes on first run)..."
    [[ -f "$IMAGE_TAR" ]] || die "Image archive not found: $IMAGE_TAR"
    docker load -i "$IMAGE_TAR"
    echo ">>> Images loaded."
else
    echo ">>> Images already present — skipping load."
fi

# ── 2. Start services ──────────────────────────────────────────────────────
echo ">>> Starting V-Sentinel stack..."
docker compose -f "$COMPOSE_FILE" --project-directory "$USB_DIR" up -d

# ── 3. Wait for Django ─────────────────────────────────────────────────────
echo ">>> Waiting for Django to be ready..."
ATTEMPTS=0
until curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/admin/ 2>/dev/null | grep -qE "^(200|301|302)"; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [[ $ATTEMPTS -ge 30 ]]; then
        die "Django did not become ready after 60 seconds. Check: docker logs vsentinel-django"
    fi
    sleep 2
done
echo ">>> Django is ready."

# ── 4. Seed demo data ──────────────────────────────────────────────────────
echo ">>> Seeding demo data..."
"$USB_DIR/demos/demo_ctl.sh" seed

# ── 5. Print access info ───────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║          V-Sentinel Demo Stack is RUNNING            ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Django Admin   http://localhost:8000/admin/         ║"
echo "║  MiniFW Web     http://localhost:8080                ║"
echo "║                                                      ║"
echo "║  Login: admin / admin123                             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Press Ctrl+C or run ./stop.sh to shut down."

trap 'echo ""; echo ">>> Run ./stop.sh to stop all containers."' EXIT

# Keep running so Ctrl+C is catchable
while true; do sleep 60; done
