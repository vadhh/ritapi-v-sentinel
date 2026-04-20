# ritapi-v-sentinel USB Demo Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package ritapi-v-sentinel into a self-contained USB demo kit that a salesperson can run with a single `./demo.sh` on Windows WSL2 or Linux, fully offline.

**Architecture:** Two USB-specific Dockerfiles bake the Django and MiniFW source into their images (the production compose mounts source at runtime — USB cannot do that). A build script pulls all 4 images, saves them to a single tar, and stages the USB directory. A smart launcher loads images only if absent, starts services, polls for readiness, seeds demo data, and prints URLs.

**Tech Stack:** Docker, Docker Compose v2, Bash, Python 3.11-slim (base images)

---

## File Map

| Status | Path | Responsibility |
|---|---|---|
| Create | `docker/Dockerfile.django.usb` | Django image with source baked in |
| Create | `docker/Dockerfile.minifw.usb` | MiniFW image with source baked in |
| Create | `docker/docker-compose.usb.yml` | USB compose: image: tags, no source mounts |
| Modify | `docker-compose.yml` | Add `image:` tags to django/minifw services |
| Create | `usb/demo.sh` | Smart launcher |
| Create | `usb/stop.sh` | Clean shutdown |
| Create | `usb/README.txt` | Human instructions |
| Create | `usb/demos/demo_ctl.sh` | Seeder via docker exec (no venv) |
| Create | `build_usb.sh` | Build + stage script |
| Create | `.gitattributes` | Force LF on shell scripts |

---

### Task 1: USB Dockerfiles

**Files:**
- Create: `docker/Dockerfile.django.usb`
- Create: `docker/Dockerfile.minifw.usb`

Context: The existing `Dockerfile.django` and `Dockerfile.minifw` only install pip requirements — they do NOT copy source. The compose mounts source at runtime (`./projects/ritapi_django:/app`). For USB, we need images with source baked in because there is no source tree on the USB target.

- [ ] **Step 1: Create `docker/Dockerfile.django.usb`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY projects/ritapi_django/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY projects/ritapi_django/ /app/
```

- [ ] **Step 2: Create `docker/Dockerfile.minifw.usb`**

```dockerfile
FROM python:3.11-slim

WORKDIR /minifw_app

ENV PYTHONPATH=/minifw_app/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY projects/minifw_ai_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY projects/minifw_ai_service/ /minifw_app/
```

- [ ] **Step 3: Verify both Dockerfiles build from repo root**

Run from `/home/sydeco/ritapi-v-sentinel`:
```bash
docker build -f docker/Dockerfile.django.usb -t test-django-usb .
docker build -f docker/Dockerfile.minifw.usb -t test-minifw-usb .
```
Expected: both complete without error. Then clean up:
```bash
docker rmi test-django-usb test-minifw-usb
```

- [ ] **Step 4: Commit**

```bash
cd /home/sydeco/ritapi-v-sentinel
git add docker/Dockerfile.django.usb docker/Dockerfile.minifw.usb
git commit -m "feat(usb): USB Dockerfiles bake source into images"
```

---

### Task 2: USB Compose File + Base Compose image: Tags

**Files:**
- Create: `docker/docker-compose.usb.yml`
- Modify: `docker-compose.yml` (add `image:` tags to django, minifw-daemon, minifw-web)

Context: The USB compose must use `image:` instead of `build:` so it can run from the tar-loaded images. The base `docker-compose.yml` needs `image:` tags so `docker tag` works reliably in the build script. Container names on django and minifw-daemon are pinned so `docker exec` in demo_ctl.sh is reliable. `--project-directory` is passed by the launcher to resolve `./` volume paths from USB root.

- [ ] **Step 1: Add `image:` tags to `docker-compose.yml`**

Open `docker-compose.yml`. Add one `image:` line to each of the three custom services:

```yaml
  django:
    build:
      context: .
      dockerfile: docker/Dockerfile.django
    image: ritapi-v-sentinel/django:latest   # ← add this line
    command: sh /entrypoint.sh
    working_dir: /app
    volumes:
      - ./projects/ritapi_django:/app
      - ./docker/entrypoint-django.sh:/entrypoint.sh:ro
      - minifw_logs:/minifw/logs
    ports:
      - "8000:8000"
    env_file: docker/demo.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  minifw-daemon:
    build:
      context: .
      dockerfile: docker/Dockerfile.minifw
    image: ritapi-v-sentinel/minifw:latest   # ← add this line
    command: >
      sh -c "mkdir -p /minifw/logs && python -m minifw_ai"
    working_dir: /minifw_app
    volumes:
      - ./projects/minifw_ai_service:/minifw_app
      - minifw_logs:/minifw/logs
    env_file: docker/demo.env

  minifw-web:
    build:
      context: .
      dockerfile: docker/Dockerfile.minifw
    image: ritapi-v-sentinel/minifw:latest   # ← add this line (same tag — same image)
    command: >
      uvicorn app.web.app:app
      --host 0.0.0.0
      --port 8080
      --reload
      --reload-dir /minifw_app/app
    working_dir: /minifw_app
    volumes:
      - ./projects/minifw_ai_service:/minifw_app
      - minifw_logs:/minifw/logs
    ports:
      - "8080:8080"
    env_file: docker/demo.env
    depends_on:
      - minifw-daemon
```

The full modified `docker-compose.yml` (replace file contents entirely):

```yaml
services:

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ritapi_v_sentinel
      POSTGRES_USER: ritapi
      POSTGRES_PASSWORD: demo_db_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ritapi -d ritapi_v_sentinel"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine

  django:
    build:
      context: .
      dockerfile: docker/Dockerfile.django
    image: ritapi-v-sentinel/django:latest
    command: sh /entrypoint.sh
    working_dir: /app
    volumes:
      - ./projects/ritapi_django:/app
      - ./docker/entrypoint-django.sh:/entrypoint.sh:ro
      - minifw_logs:/minifw/logs
    ports:
      - "8000:8000"
    env_file: docker/demo.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  minifw-daemon:
    build:
      context: .
      dockerfile: docker/Dockerfile.minifw
    image: ritapi-v-sentinel/minifw:latest
    command: >
      sh -c "mkdir -p /minifw/logs && python -m minifw_ai"
    working_dir: /minifw_app
    volumes:
      - ./projects/minifw_ai_service:/minifw_app
      - minifw_logs:/minifw/logs
    env_file: docker/demo.env

  minifw-web:
    build:
      context: .
      dockerfile: docker/Dockerfile.minifw
    image: ritapi-v-sentinel/minifw:latest
    command: >
      uvicorn app.web.app:app
      --host 0.0.0.0
      --port 8080
      --reload
      --reload-dir /minifw_app/app
    working_dir: /minifw_app
    volumes:
      - ./projects/minifw_ai_service:/minifw_app
      - minifw_logs:/minifw/logs
    ports:
      - "8080:8080"
    env_file: docker/demo.env
    depends_on:
      - minifw-daemon

volumes:
  postgres_data:
  minifw_logs:
```

- [ ] **Step 2: Create `docker/docker-compose.usb.yml`**

```yaml
# USB demo stack — images pre-loaded from images/vsentinel.tar
# Run via: usb/demo.sh (handles image load, up, seed)

services:

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ritapi_v_sentinel
      POSTGRES_USER: ritapi
      POSTGRES_PASSWORD: demo_db_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ritapi -d ritapi_v_sentinel"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine

  django:
    image: ritapi-v-sentinel/django:usb
    container_name: vsentinel-django
    command: sh /entrypoint.sh
    working_dir: /app
    volumes:
      - ./docker/entrypoint-django.sh:/entrypoint.sh:ro
      - minifw_logs:/minifw/logs
    ports:
      - "8000:8000"
    env_file: docker/demo.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  minifw-daemon:
    image: ritapi-v-sentinel/minifw:usb
    container_name: vsentinel-minifw-daemon
    command: >
      sh -c "mkdir -p /minifw/logs && python -m minifw_ai"
    working_dir: /minifw_app
    volumes:
      - minifw_logs:/minifw/logs
    env_file: docker/demo.env

  minifw-web:
    image: ritapi-v-sentinel/minifw:usb
    command: >
      uvicorn app.web.app:app
      --host 0.0.0.0
      --port 8080
    working_dir: /minifw_app
    volumes:
      - minifw_logs:/minifw/logs
    ports:
      - "8080:8080"
    env_file: docker/demo.env
    depends_on:
      - minifw-daemon

volumes:
  postgres_data:
  minifw_logs:
```

Note: `--reload` and `--reload-dir` are removed from minifw-web since there is no source tree to watch on USB.

- [ ] **Step 3: Verify compose file is valid**

```bash
cd /home/sydeco/ritapi-v-sentinel
docker compose -f docker/docker-compose.usb.yml config
```
Expected: YAML printed with no error. (Images not present yet — that is OK, `config` only validates syntax.)

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml docker/docker-compose.usb.yml
git commit -m "feat(usb): USB compose + image: tags on base compose"
```

---

### Task 3: USB Launcher (`usb/demo.sh`)

**Files:**
- Create: `usb/demo.sh`

Context: The launcher must work from any mount path. It uses `BASH_SOURCE[0]` to self-locate. Images are loaded only if any tagged image is missing (smart check avoids multi-minute re-loads on re-runs). Django readiness is polled via HTTP on port 8000. After Django is up, demo data is seeded. An EXIT trap reminds the user how to stop.

- [ ] **Step 1: Create `usb/demo.sh`**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x /home/sydeco/ritapi-v-sentinel/usb/demo.sh
```

- [ ] **Step 3: Commit**

```bash
cd /home/sydeco/ritapi-v-sentinel
git add usb/demo.sh
git commit -m "feat(usb): smart launcher demo.sh"
```

---

### Task 4: USB Stop Script (`usb/stop.sh`)

**Files:**
- Create: `usb/stop.sh`

- [ ] **Step 1: Create `usb/stop.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USB_DIR="$SCRIPT_DIR"
COMPOSE_FILE="$USB_DIR/docker/docker-compose.usb.yml"

echo ">>> Stopping V-Sentinel demo stack..."
docker compose -f "$COMPOSE_FILE" --project-directory "$USB_DIR" down
echo ">>> Done."
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x /home/sydeco/ritapi-v-sentinel/usb/stop.sh
cd /home/sydeco/ritapi-v-sentinel
git add usb/stop.sh
git commit -m "feat(usb): stop.sh shutdown script"
```

---

### Task 5: USB Demo Controller (`usb/demos/demo_ctl.sh`)

**Files:**
- Create: `usb/demos/demo_ctl.sh`

Context: The original `demos/demo_ctl.sh` resolves a Python venv or system Python and runs `demo_ritapi_dashboard.py` directly. On USB there is no venv and no source tree accessible from the host. Instead, this USB adapter uses `docker exec vsentinel-django python manage.py shell -c "..."` to run seed/reset logic inside the running Django container. The container name `vsentinel-django` is pinned in `docker/docker-compose.usb.yml`.

The seed logic is inlined (no import of demo_ritapi_dashboard.py) to avoid path resolution issues. Data seeded: 20 alerts, 100 request logs, 10 blocked IPs with geo coords, 5 ASN entries, demo IpReputation records. This matches the original demo_ritapi_dashboard.py content.

- [ ] **Step 1: Verify model field names**

Read the actual model files before writing the seed script. Field names below are based on reading `demos/demo_ritapi_dashboard.py` — confirm they match:

```bash
grep -n "class BlockedIP\|country_name\|lat\|lon" /home/sydeco/ritapi-v-sentinel/projects/ritapi_django/blocking/models.py
grep -n "class IpReputation\|reputation\|score" /home/sydeco/ritapi-v-sentinel/projects/ritapi_django/ip_reputation/models.py
grep -n "class AsnTrustConfig\|trusted" /home/sydeco/ritapi-v-sentinel/projects/ritapi_django/asn/models.py
```

Adjust field names in the seed script below to match what these greps show. If a field does not exist (e.g., `lat`/`lon` not on `BlockedIP`), remove it from the seed data; the demo still works with fewer fields shown.

- [ ] **Step 2: Create `usb/demos/demo_ctl.sh`**

```bash
#!/usr/bin/env bash
# USB-specific demo controller — uses docker exec, no venv needed.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

CONTAINER="vsentinel-django"

die() { echo "ERROR: $*" >&2; exit 1; }

docker inspect "$CONTAINER" >/dev/null 2>&1 || die "Container '$CONTAINER' is not running. Run ./demo.sh first."

SEED_SCRIPT='
import random
from datetime import timedelta
from django.utils import timezone
from alert.models import Alert
from blocking.models import BlockedIP
from log_channel.models import RequestLog
from minifw.models import MiniFWEvent, MiniFWBlockedIP, AuditLog
from asn.models import AsnInfo, AsnTrustConfig
from ip_reputation.models import IpReputation

def seed():
    print("Clearing existing demo data...")
    Alert.objects.all().delete()
    RequestLog.objects.all().delete()
    MiniFWEvent.objects.all().delete()
    MiniFWBlockedIP.objects.all().delete()
    BlockedIP.objects.all().delete()
    AuditLog.objects.all().delete()

    print("Seeding alerts...")
    severities = ["low", "medium", "high", "critical"]
    types = ["SQL Injection Attempt", "Brute Force Attack", "Malware Beacon", "Unauthorized Access", "DDoS Burst"]
    ips = ["192.168.1.10", "45.33.22.11", "10.0.0.5", "185.22.33.44", "99.88.77.66"]
    for _ in range(20):
        Alert.objects.create(
            alert_type=random.choice(types),
            ip_address=random.choice(ips),
            detail=f"Detected suspicious activity from {random.choice(ips)} targeting internal resources.",
            severity=random.choice(severities),
            resolved=random.choice([True, False]),
        )

    print("Seeding request logs...")
    actions = ["ALLOW", "BLOCK", "MONITOR"]
    methods = ["GET", "POST", "PUT", "DELETE"]
    paths = ["/api/v1/user", "/login", "/api/v1/data", "/admin", "/static/js/app.js", "/.env", "/wp-admin"]
    log_ips = ["192.168.1.100", "10.0.0.50", "172.16.0.5", "45.33.22.11", "185.22.33.44"]
    now = timezone.now()
    for i in range(100):
        action = random.choice(actions)
        score = random.uniform(0.7, 1.0) if action == "BLOCK" else random.uniform(0.0, 0.4)
        RequestLog.objects.create(
            ip_address=random.choice(log_ips),
            path=random.choice(paths),
            method=random.choice(methods),
            body_size=random.randint(0, 5000),
            score=score,
            label="clean" if action == "ALLOW" else "threat",
            action=action,
            reasons="Normal traffic" if action == "ALLOW" else "Pattern matched malicious signature",
            timestamp=now - timedelta(minutes=i * 5),
        )

    print("Seeding blocked IPs...")
    targets = [
        ("45.33.22.11", "Known C2 server", "Russia", "RU", 55.75, 37.61),
        ("185.22.33.44", "Tor exit node", "Netherlands", "NL", 52.37, 4.89),
        ("99.88.77.66", "Scanner", "China", "CN", 39.91, 116.39),
        ("103.5.6.7", "Brute force origin", "Vietnam", "VN", 21.03, 105.85),
        ("91.121.4.5", "Malware C2", "France", "FR", 48.86, 2.35),
        ("77.88.99.11", "DDoS participant", "Ukraine", "UA", 50.45, 30.52),
        ("5.6.7.8", "SQL scanner", "Germany", "DE", 52.52, 13.40),
        ("203.11.22.33", "Port scanner", "South Korea", "KR", 37.57, 126.98),
        ("122.4.5.6", "Credential stuffing", "India", "IN", 28.61, 77.20),
        ("196.2.3.4", "Phishing origin", "Nigeria", "NG", 9.06, 7.49),
    ]
    for ip, reason, country_name, country, lat, lon in targets:
        BlockedIP.objects.get_or_create(
            ip_address=ip,
            defaults=dict(reason=reason, country_name=country_name, country=country, lat=lat, lon=lon),
        )

    print("Seeding ASN info...")
    asns = [
        (12345, "ExampleNet", "US", "ISP", True),
        (67890, "MaliciousHosting", "RU", "Hosting", False),
        (11111, "CloudProvider", "NL", "Cloud", True),
        (22222, "TorNetwork", "DE", "VPN", False),
        (33333, "EducationNet", "AU", "Education", True),
    ]
    for asn_num, name, country, asn_type, trusted in asns:
        obj, _ = AsnInfo.objects.get_or_create(asn=asn_num, defaults=dict(name=name, country=country, asn_type=asn_type))
        AsnTrustConfig.objects.get_or_create(asn_info=obj, defaults=dict(trusted=trusted))

    print("Seeding IP reputation...")
    rep_ips = [
        ("45.33.22.11", "malicious", 95),
        ("185.22.33.44", "suspicious", 72),
        ("192.168.1.100", "clean", 5),
        ("10.0.0.50", "clean", 2),
    ]
    for ip, rep, score in rep_ips:
        IpReputation.objects.get_or_create(ip_address=ip, defaults=dict(reputation=rep, score=score))

    print("Demo data seeded successfully.")

seed()
'

RESET_SCRIPT='
from alert.models import Alert
from blocking.models import BlockedIP
from log_channel.models import RequestLog
from minifw.models import MiniFWEvent, MiniFWBlockedIP, AuditLog
Alert.objects.all().delete()
RequestLog.objects.all().delete()
MiniFWEvent.objects.all().delete()
MiniFWBlockedIP.objects.all().delete()
BlockedIP.objects.all().delete()
AuditLog.objects.all().delete()
print("Demo data cleared.")
'

case "${1:-}" in
    seed)
        echo -e "${BLUE}>>> Injecting V-Sentinel demo data...${NC}"
        docker exec "$CONTAINER" python manage.py shell -c "$SEED_SCRIPT"
        echo -e "${GREEN}>>> Done.${NC}"
        ;;
    reset)
        echo -e "${RED}>>> Removing V-Sentinel demo data...${NC}"
        docker exec "$CONTAINER" python manage.py shell -c "$RESET_SCRIPT"
        echo -e "${GREEN}>>> Done.${NC}"
        ;;
    *)
        echo "Usage: $0 {seed|reset}"
        echo "  seed  - Inject realistic sample data into existing database"
        echo "  reset - Wipe sample logs/alerts for a fresh start"
        exit 1
        ;;
esac
```

- [ ] **Step 3: Make executable and commit**

```bash
chmod +x /home/sydeco/ritapi-v-sentinel/usb/demos/demo_ctl.sh
cd /home/sydeco/ritapi-v-sentinel
git add usb/demos/demo_ctl.sh
git commit -m "feat(usb): demo_ctl.sh via docker exec — no venv dependency"
```

---

### Task 6: README (`usb/README.txt`)

**Files:**
- Create: `usb/README.txt`

- [ ] **Step 1: Create `usb/README.txt`**

```
V-SENTINEL USB DEMO
===================

Prerequisites
-------------
- Docker Desktop running (Windows: Docker Desktop with WSL2 integration enabled)
- OR Docker Engine running (Linux)

Quick Start
-----------
1. Open a terminal (Windows: open WSL2 terminal)
2. Navigate to this USB drive:
     cd /path/to/usb    (Linux)
     cd /mnt/d/         (WSL2 — adjust drive letter)
3. Run the demo:
     bash demo.sh

   First run loads Docker images (~2-4 GB). Subsequent runs are instant.

4. Open your browser:
     Django Admin:  http://localhost:8000/admin/
     MiniFW Web:    http://localhost:8080/

   Login: admin / admin123

Stop the Demo
-------------
    bash stop.sh

Or press Ctrl+C in the demo.sh terminal, then run bash stop.sh.

Reset Demo Data
---------------
    bash demos/demo_ctl.sh reset
    bash demos/demo_ctl.sh seed

Troubleshooting
---------------
- "Docker is not running": Start Docker Desktop and wait for it to fully start.
- "Container not ready after 60s": Run `docker logs vsentinel-django` to see errors.
- Port 8000 or 8080 in use: Stop any other running Docker stacks first.
```

- [ ] **Step 2: Commit**

```bash
cd /home/sydeco/ritapi-v-sentinel
git add usb/README.txt
git commit -m "feat(usb): README.txt with quick start instructions"
```

---

### Task 7: Build Script (`build_usb.sh`)

**Files:**
- Create: `build_usb.sh`

Context: Must be run from repo root (`/home/sydeco/ritapi-v-sentinel`). Builds two custom images with USB tags, pulls postgres and redis, saves all four to a single tar, then stages the full USB layout to `dist/usb-vsentinel/`. The developer then copies `dist/usb-vsentinel/` contents to the USB drive.

- [ ] **Step 1: Create `build_usb.sh`**

```bash
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
cp usb/demo.sh  "$STAGE_DIR/demo.sh"
cp usb/stop.sh  "$STAGE_DIR/stop.sh"
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
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x /home/sydeco/ritapi-v-sentinel/build_usb.sh
cd /home/sydeco/ritapi-v-sentinel
git add build_usb.sh
git commit -m "feat(usb): build_usb.sh — builds and stages USB demo kit"
```

---

### Task 8: `.gitattributes` (prevent CRLF corruption)

**Files:**
- Create or modify: `.gitattributes`

Context: Windows git clients can rewrite shell scripts with CRLF line endings, which breaks `bash` on Linux/WSL2. `.gitattributes` forces LF for all relevant files.

- [ ] **Step 1: Check if `.gitattributes` already exists**

```bash
ls /home/sydeco/ritapi-v-sentinel/.gitattributes 2>/dev/null && echo "exists" || echo "not found"
```

- [ ] **Step 2: Create or append `.gitattributes`**

If not found, create:

```
* text=auto

usb/demo.sh                     text eol=lf
usb/stop.sh                     text eol=lf
usb/demos/demo_ctl.sh           text eol=lf
build_usb.sh                    text eol=lf
docker/entrypoint-django.sh     text eol=lf
demos/demo_ctl.sh               text eol=lf
demos/demo_traffic_gen.sh       text eol=lf
```

If it already exists, append the `usb/` and `build_usb.sh` lines without duplicating existing entries.

- [ ] **Step 3: Commit**

```bash
cd /home/sydeco/ritapi-v-sentinel
git add .gitattributes
git commit -m "chore: gitattributes enforce LF for all shell scripts"
```

---

## Verification

After all tasks complete, run the full build end-to-end:

```bash
cd /home/sydeco/ritapi-v-sentinel
bash build_usb.sh
```

Expected output ends with the staged directory path and `rsync` instructions.

Spot-check the staged layout:
```bash
find dist/usb-vsentinel -type f | sort
```

Expected:
```
dist/usb-vsentinel/README.txt
dist/usb-vsentinel/demos/demo_ctl.sh
dist/usb-vsentinel/demo.sh
dist/usb-vsentinel/docker/demo.env
dist/usb-vsentinel/docker/docker-compose.usb.yml
dist/usb-vsentinel/docker/entrypoint-django.sh
dist/usb-vsentinel/images/vsentinel.tar
dist/usb-vsentinel/stop.sh
```

Verify tar contains all 4 images:
```bash
docker inspect --type=image \
  ritapi-v-sentinel/django:usb \
  ritapi-v-sentinel/minifw:usb \
  postgres:16-alpine \
  redis:7-alpine \
  | python3 -c "import sys,json; imgs=json.load(sys.stdin); [print(i['RepoTags']) for i in imgs]"
```
Expected: 4 non-empty tag lists printed.
