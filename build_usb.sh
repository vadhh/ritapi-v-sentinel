#!/usr/bin/env bash
# Build and stage the V-Sentinel USB demo kit.
# Run from repo root: bash build_usb.sh
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STAGE_DIR="$SCRIPT_DIR/dist/usb-vsentinel"

DJANGO_TAG="ritapi-v-sentinel/django:usb"
MINIFW_TAG="ritapi-v-sentinel/minifw:usb"
POSTGRES_TAG="postgres:16-alpine"
REDIS_TAG="redis:7-alpine"

die() { echo "ERROR: $*" >&2; exit 1; }

cd "$SCRIPT_DIR"

[[ -f "docker/Dockerfile.django.usb" ]] || die "docker/Dockerfile.django.usb not found — run from repo root"
[[ -f "docker/Dockerfile.minifw.usb" ]] || die "docker/Dockerfile.minifw.usb not found — run from repo root"
[[ -d "projects/ritapi_django" ]]        || die "projects/ritapi_django/ not found"
[[ -d "projects/minifw_ai_service" ]]    || die "projects/minifw_ai_service/ not found"

docker info >/dev/null 2>&1 || die "Docker is not running"

# ── 1. Pull base images ────────────────────────────────────────────────────
echo ">>> Pulling $POSTGRES_TAG ..."
docker pull "$POSTGRES_TAG"

echo ">>> Pulling $REDIS_TAG ..."
docker pull "$REDIS_TAG"

# ── 2. Build USB images ────────────────────────────────────────────────────
echo ">>> Building Django USB image ($DJANGO_TAG) ..."
docker build -f docker/Dockerfile.django.usb -t "$DJANGO_TAG" .

echo ">>> Building MiniFW USB image ($MINIFW_TAG) ..."
docker build -f docker/Dockerfile.minifw.usb -t "$MINIFW_TAG" .

# ── 3. Save all images to tar ──────────────────────────────────────────────
mkdir -p "$STAGE_DIR/images"
echo ">>> Saving images to $STAGE_DIR/images/vsentinel.tar ..."
docker save \
    "$DJANGO_TAG" \
    "$MINIFW_TAG" \
    "$POSTGRES_TAG" \
    "$REDIS_TAG" \
    -o "$STAGE_DIR/images/vsentinel.tar"
echo ">>> Tar size: $(du -sh "$STAGE_DIR/images/vsentinel.tar" | cut -f1)"

# ── 4. Stage USB files ─────────────────────────────────────────────────────
echo ">>> Staging USB layout to $STAGE_DIR/ ..."

# Launcher scripts
cp usb/demo.sh    "$STAGE_DIR/demo.sh"
cp usb/stop.sh    "$STAGE_DIR/stop.sh"
cp usb/README.txt "$STAGE_DIR/README.txt"

# Docker artefacts
mkdir -p "$STAGE_DIR/docker"
cp docker/docker-compose.usb.yml    "$STAGE_DIR/docker/docker-compose.usb.yml"
cp docker/demo.env                  "$STAGE_DIR/docker/demo.env"
cp docker/entrypoint-django.sh      "$STAGE_DIR/docker/entrypoint-django.sh"

# Demo controller
mkdir -p "$STAGE_DIR/demos"
cp usb/demos/demo_ctl.sh  "$STAGE_DIR/demos/demo_ctl.sh"

# Force LF on all shell scripts in stage dir
if command -v sed >/dev/null 2>&1; then
    find "$STAGE_DIR" -name "*.sh" -exec sed -i 's/\r//' {} +
    sed -i 's/\r//' "$STAGE_DIR/docker/entrypoint-django.sh"
fi

# Ensure execute bits
chmod +x "$STAGE_DIR/demo.sh" \
         "$STAGE_DIR/stop.sh" \
         "$STAGE_DIR/demos/demo_ctl.sh" \
         "$STAGE_DIR/docker/entrypoint-django.sh"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     V-Sentinel USB kit staged successfully!          ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Output: $STAGE_DIR"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Copy all files from that directory to the USB root:"
echo "  rsync -av --progress $STAGE_DIR/ /media/\$USER/USB_NAME/"
echo ""
echo "On the USB: run  bash demo.sh"
