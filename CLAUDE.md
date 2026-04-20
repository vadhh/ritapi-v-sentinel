# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RITAPI V-Sentinel is a network security enforcement platform with two main services:

1. **RITAPI Django Dashboard** (`projects/ritapi_django/`) — Web-based ops dashboard (Django 4.2 + DRF, PostgreSQL, Redis) served via Gunicorn on port 8000
2. **MiniFW-AI Service** (`projects/minifw_ai_service/`) — Real-time security engine (FastAPI + daemon) with DNS event processing, flow tracking, MLP inference, YARA scanning, and nftables enforcement; served via Uvicorn on port 8080

Both services sit behind Nginx and run as systemd units. The unified config lives at `/etc/ritapi/vsentinel.env` (template: `scripts/vsentinel.env.template`).

## Critical Constraint: install.sh Compatibility

All code modifications MUST remain compatible with `install.sh`. The installer runs on fresh VMs with `set -e` (exits on any error). Breaking the installer means breaking production deployments.

### Directory Structure the Installer Expects
```
projects/
├── ritapi_django/
│   ├── manage.py                    # Verified by verify_package_structure()
│   ├── requirements.txt             # pip install -r in install_ritapi_django()
│   └── ritapi_v_sentinel/
│       └── wsgi.py                  # Gunicorn entry: ritapi_v_sentinel.wsgi:application
└── minifw_ai_service/
    ├── app/                         # Detected and copied by install_minifw_ai()
    │   └── minifw_ai/               # Entry: python -m minifw_ai
    ├── requirements.txt             # pip install -r in install_minifw_ai()
    └── config/                      # policy.json and feeds/ created if missing
scripts/
├── vsentinel.env.template           # Copied to /etc/ritapi/vsentinel.env
├── vsentinel_selftest.sh            # Post-install verification
├── vsentinel_runtime_guard.sh       # Copied to /opt/minifw_ai/scripts/
├── vsentinel_scope_gate.sh          # Scope validation (blocks install on failure)
└── minifw_fixed/                    # CRUD fix overlay (MUST stay in sync with minifw/ app)
```

### minifw_fixed Overlay Sync
`scripts/minifw_fixed/` contains overlay files that `apply_minifw_crud_fix()` copies over the deployed Django minifw app. **These files MUST be kept in sync with `projects/ritapi_django/minifw/`**. If you modify `minifw/views.py`, `minifw/services.py`, or minifw templates, you MUST also update the corresponding files in `scripts/minifw_fixed/`. Failure to sync causes `AttributeError` crashes at runtime because `urls.py` references views that the overlay's old `views.py` doesn't define.

### What Will Break the Installer
- Renaming or moving `projects/ritapi_django/manage.py` — `verify_package_structure()` will `exit 1`
- Changing the Django WSGI module path from `ritapi_v_sentinel.wsgi:application` — Gunicorn service fails
- Changing the MiniFW entry point from `python -m minifw_ai` — systemd unit fails to start
- Adding new Python packages that require system-level C libraries not in the `apt-get install` list (python3-dev, build-essential, libpq-dev, postgresql are the only build deps installed)
- Removing `requirements.txt` from either project
- Changing `PYTHONPATH` expectations — systemd unit hardcodes `PYTHONPATH=/opt/minifw_ai/app`
- Adding mandatory env vars without updating `scripts/vsentinel.env.template` — the installer copies this template to `/etc/ritapi/vsentinel.env` and auto-generates only `DJANGO_SECRET_KEY`, `MINIFW_SECRET_KEY`, `MINIFW_ADMIN_PASSWORD`, `DB_PASSWORD`
- Writing config to `$DJANGO_PROJECT_DIR/.env` instead of `/etc/ritapi/vsentinel.env` — Django reads only the unified env file in production; the local `.env` is ignored when `/etc/ritapi/vsentinel.env` exists

### Deployment Paths (Hardcoded in install.sh)
- Django → `/opt/ritapi_v_sentinel` (owned by www-data)
- MiniFW → `/opt/minifw_ai` (owned by www-data)
- Config → `/etc/ritapi/vsentinel.env` (mode 0640, root:www-data)
- Logs → `/var/log/ritapi/`, `/opt/minifw_ai/logs/`
- Systemd → `ritapi-gunicorn.service`, `minifw-ai.service`

### Installation Flow (in order)
1. `verify_package_structure` → `detect_web_user` → `detect_dns_environment`
2. `create_vsentinel_env` (copies template, generates secrets, applies DNS config)
3. `install_system_dependencies` → `ensure_firewall_deps` (nftables, ipset)
4. `setup_postgresql` (start PostgreSQL, create DB user + database from env credentials)
5. `install_ritapi_django` (copy, venv, pip, migrate, collectstatic)
6. `install_minifw_ai` (copy, venv, pip, create default config if missing, ipset, systemd)
7. `apply_minifw_crud_fix` → `install_gunicorn_service` → `ensure_allowed_hosts` → `configure_nginx`
8. `run_scope_gate` → `install_runtime_guard` → `create_admin_user`
9. `start_services` (PostgreSQL, Redis, MiniFW-AI, Gunicorn, Nginx) → `verify_telemetry` → `run_selftest` → `post_install_verify`

### Testing Installer Compatibility
After any structural change, verify: (1) `verify_package_structure` assertions still pass, (2) both `requirements.txt` are pip-installable in a clean venv, (3) `python -m minifw_ai` and `manage.py check` still work, (4) `post_install_verify` service checks pass.

## Build & Run Commands

### Docker Demo Stack (no kernel dependencies)
```bash
docker compose up --build
# Django hot-reload: http://localhost:8000
# MiniFW web admin: http://localhost:8080

# Seed demo data
docker compose exec django python ../../demos/demo_ritapi_dashboard.py

# Reset demo data
docker compose exec django python ../../demos/demo_ritapi_dashboard.py --reset
```

Runs with `DEGRADED_MODE=1`, `MINIFW_DNS_SOURCE=none`, `MINIFW_ENFORCE=0` (observe-only — no nftables required). Config in `docker/demo.env`. Django templates and MiniFW app code reload on save via volume mounts.

`MINIFW_ENFORCE=0` is a Docker/demo-only flag added to `main.py` that skips nftables init at startup and `ipset_add` in the event loop. Never use it in production.

### Django Dashboard
```bash
cd projects/ritapi_django
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# Production: gunicorn --workers 3 --bind 127.0.0.1:8000 ritapi_v_sentinel.wsgi:application
```

### MiniFW-AI Service
```bash
cd projects/minifw_ai_service
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Required env vars:
export MINIFW_SECRET_KEY=test-secret
export MINIFW_ADMIN_PASSWORD=test-pass
# Run daemon:
python -m minifw_ai
# Run web admin:
uvicorn app.web.app:app --host 0.0.0.0 --port 8000
```

### Full Installation
```bash
sudo ./install.sh          # Interactive menu
sudo ./install.sh install  # Direct install
sudo ./install.sh status   # Check services
```

## Testing

### Django Tests (uses in-memory SQLite)
```bash
cd projects/ritapi_django
python manage.py test              # All tests
python manage.py test alert        # Single app
python manage.py test asn
python manage.py test ip_reputation
```

### MiniFW-AI Tests
```bash
cd projects/minifw_ai_service
export MINIFW_SECRET_KEY=test-secret-key
export MINIFW_ADMIN_PASSWORD=test-admin-pass
pytest testing/ -v                              # All tests
pytest testing/test_mlp_inference.py -v          # Single test file
pytest testing/ -v --cov=app --cov-report=term   # With coverage
```

## CI/CD Pipeline

GitHub Actions (`.github/workflows/pre-flight-check.yml`) runs on push to main/master/develop and PRs. Jobs: security audit (detect-secrets, pip-audit, Bandit), code quality (flake8, black), MiniFW pytest, Django tests (with PostgreSQL + Redis services).

## Architecture

### Django Apps
- `authentication/` — Login/logout + OpsAuth middleware
- `asn/`, `ip_reputation/`, `alert/`, `blocking/` — Core security modules
- `minifw/` — MiniFW-AI integration: CRUD, events viewer, audit logs, user management with 5-tier RBAC, sector lock
- `ops/` — Operations sub-dashboards (ops_asn, ops_iprep, ops_json, ops_alert, ops_blocking, ops_geoblock)
- `middlewares/` — Rate limiting (`rate_limit.py`) and security enforcement (`security_enforcement.py`)
- `log_channel/` — Request logging

### MiniFW-AI Core (`app/minifw_ai/`)
- `main.py` — Event loop + multi-layer scoring pipeline; enforces `GAMBLING_ONLY=1` hard guard
- `enforce.py` — nftables/ipset enforcement with input validation
- `policy.py` — JSON-based policy configuration loader
- `feeds.py` — Domain/IP/ASN allow/deny list matching
- `burst.py` — Rate/burst detection
- `collector_dnsmasq.py` — DNS event stream (file/journald/UDP/none backends)
- `collector_zeek.py` — TLS SNI collection
- `collector_flow.py` — Conntrack-based flow tracking with LRU eviction
- `sector_lock.py` — Factory-set immutable sector configuration
- `utils/mlp_engine.py` — MLP neural network anomaly detector
- `utils/yara_scanner.py` — YARA rule pattern matching

### MiniFW-AI Web (`app/web/`)
- FastAPI admin interface with JWT auth (`app/middleware/auth_middleware.py`)
- RBAC via `app/services/rbac_service.py`
- SQLAlchemy models in `app/models/`, Pydantic schemas in `app/schemas/`

### Key Design Patterns
- **Event-driven**: MiniFW daemon runs a continuous event loop consuming DNS queries and network flows
- **Multi-layer scoring**: Threat scores from DNS feeds, TLS SNI, ASN, burst detection, MLP, YARA
- **Hard threat gates**: PPS saturation, burst flood, bot-like patterns override normal scoring
- **Sector lock**: Immutable factory-set config prevents runtime tampering
- **Graceful degradation**: `DEGRADED_MODE=1` allows operation without all telemetry sources
- **GAMBLING_ONLY enforcement**: Hard-coded regulatory constraint in `main.py` — must be `1`

## Key Configuration Files
- `scripts/vsentinel.env.template` — All environment variables for both services
- `projects/minifw_ai_service/config/policy.json` — MiniFW policy thresholds
- `projects/minifw_ai_service/config/feeds/` — Allow/deny domain lists
- `projects/minifw_ai_service/config/sector_lock.json` — Sector configuration
- `projects/ritapi_django/ritapi_v_sentinel/settings.py` — Django settings

## Operational Scripts
- `vsentinel-audit.sh` — Integration audit
- `scripts/vsentinel_selftest.sh` — Post-install verification
- `scripts/vsentinel_runtime_guard.sh` — Pre-start runtime checks
- `scripts/vsentinel_scope_gate.sh` — Scope validation
