# USB Demo Kit — ritapi-v-sentinel Design Spec

**Date:** 2026-04-20  
**Project:** ritapi-v-sentinel  
**Status:** Approved

---

## Problem

Sales team needs to demo ritapi-v-sentinel on a USB key — offline, on Windows WSL2 or Linux, with a single `./demo.sh` command. The demo must be completely self-contained (no internet required) and work from any USB mount path.

## Constraints

- 8 GB USB, 1 USB per product
- Target: sales team laptops (Windows WSL2 or Linux)
- NOT handed directly to clients
- Offline-only: all Docker images pre-bundled
- Manual run: salesperson types one command
- Source volumes are mounted at runtime in the existing compose — must be baked into images for USB

---

## Key Challenge: Source Volume Mounts

The existing `docker-compose.yml` mounts source code at runtime:
- `./projects/ritapi_django:/app` → django container
- `./projects/minifw_ai_service:/minifw_app` → minifw-daemon and minifw-web

The existing `Dockerfile.django` and `Dockerfile.minifw` only install Python requirements; they do NOT copy source code. On USB there is no source tree, so USB-specific Dockerfiles must COPY source in at build time.

---

## USB Layout

```
USB root/
├── demo.sh                         ← smart launcher
├── stop.sh                         ← docker compose down
├── README.txt                      ← human instructions
├── images/
│   └── vsentinel.tar               ← all 4 images (~2-4 GB)
├── docker/
│   ├── docker-compose.usb.yml      ← image: tags, no source mounts, container_name set
│   ├── demo.env                    ← copied from docker/demo.env
│   └── entrypoint-django.sh        ← copied from docker/entrypoint-django.sh
└── demos/
    └── demo_ctl.sh                 ← USB adapter (docker exec, no venv)
```

---

## Images

| Image | Tag | Built from |
|---|---|---|
| ritapi-v-sentinel/django | usb | docker/Dockerfile.django.usb |
| ritapi-v-sentinel/minifw | usb | docker/Dockerfile.minifw.usb |
| postgres | 16-alpine | docker pull |
| redis | 7-alpine | docker pull |

All four saved to `images/vsentinel.tar` via `docker save`.

---

## New Files

### `docker/Dockerfile.django.usb`
Extends base Dockerfile.django: installs requirements AND copies `projects/ritapi_django/` to `/app/`.

### `docker/Dockerfile.minifw.usb`
Extends base Dockerfile.minifw: installs requirements AND copies `projects/minifw_ai_service/` to `/minifw_app/`.

### `docker/docker-compose.usb.yml`
Five services, image: tags instead of build:, no source volume mounts. Django and minifw-daemon have explicit `container_name:` for reliable `docker exec` targeting. Entrypoint script still bind-mounted from `./docker/entrypoint-django.sh`.

### `usb/demo.sh`
1. Self-locate via `BASH_SOURCE[0]`
2. Check docker daemon reachable
3. If any image missing: `docker load -i images/vsentinel.tar`
4. `docker compose -f docker/docker-compose.usb.yml --project-directory "$USB_DIR" up -d`
5. Poll `http://localhost:8000/admin/` until 200/302 (up to 60s)
6. Run `demos/demo_ctl.sh seed`
7. Print URLs and credentials
8. EXIT trap prints stop instructions

### `usb/stop.sh`
`docker compose -f docker/docker-compose.usb.yml --project-directory "$USB_DIR" down`

### `usb/README.txt`
Plain-text instructions for Windows WSL2 and Linux.

### `usb/demos/demo_ctl.sh`
USB-specific seeder. Uses `docker exec vsentinel-django python manage.py shell -c "..."` with inline Python seed/reset logic. No venv dependency. Container name `vsentinel-django` is set in docker-compose.usb.yml.

### `build_usb.sh`
At repo root. Pulls postgres:16-alpine and redis:7-alpine, builds the two USB images, saves all four to `images/vsentinel.tar`, stages the USB layout to `dist/usb-vsentinel/`.

### `.gitattributes`
Sets `text eol=lf` for all shell scripts to prevent CRLF corruption on Windows.

---

## Modifications to Existing Files

### `docker-compose.yml`
Add `image:` tags to django, minifw-daemon, minifw-web so `docker tag` works reliably in `build_usb.sh`.

---

## Success Criteria

1. `bash build_usb.sh` completes without error on developer machine
2. Resulting `dist/usb-vsentinel/` directory can be `rsync`-ed or copied to USB
3. On a clean machine (no v-sentinel images), `bash demo.sh` from USB root:
   - Loads images
   - Starts all 5 containers
   - Seeds demo data
   - Prints `http://localhost:8000` and `http://localhost:8080`
4. Django admin login with `admin` / `admin123` shows seeded data
5. MiniFW web at `:8080` shows dashboard
6. `bash stop.sh` shuts everything down cleanly
