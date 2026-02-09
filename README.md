# RITAPI V-Sentinel

Network security enforcement platform combining a Django operations dashboard with a real-time AI-powered firewall engine. Designed for regulatory compliance environments (gambling domain blocking), the system performs DNS-based domain analysis, network flow tracking, and automated IP blocking using nftables.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security Features](#security-features)
- [Operational Tooling](#operational-tooling)
- [Troubleshooting](#troubleshooting)
- [Additional Documentation](#additional-documentation)
- [License](#license)

---

## Architecture Overview

The platform consists of two main components that run as separate systemd services:

```
                           +---------------------+
                           |      Nginx          |
                           |  (Reverse Proxy)    |
                           +-----+--------+------+
                                 |        |
                    Port 8000    |        |   Port 8080
                  (Gunicorn)     |        |   (Uvicorn)
                                 v        v
              +------------------+--+  +--+------------------+
              |  RITAPI V-Sentinel  |  |  MiniFW-AI Service  |
              |  (Django Dashboard) |  |  (FastAPI + Engine)  |
              +---------------------+  +----------------------+
              | - Ops Dashboards    |  | - DNS Event Stream   |
              | - ASN Lookup        |  | - Flow Tracking      |
              | - IP Reputation     |  | - MLP Inference      |
              | - Alert Management  |  | - YARA Scanning      |
              | - JSON Schema Valid.|  | - nftables Enforce.  |
              | - Geo-Blocking      |  | - Policy Engine      |
              | - MiniFW CRUD UI    |  | - Sector Lock        |
              | - Request Logging   |  | - Audit Logging      |
              +--------+------------+  +----------+-----------+
                       |                          |
                       v                          v
                  PostgreSQL              SQLite + JSONL Logs
                  + Redis                 + nftables/ipset
```

**RITAPI V-Sentinel (Django)** provides the web-based operations dashboard for configuration management, monitoring, and reporting. It connects to PostgreSQL for persistent storage and Redis for rate limiting and caching.

**MiniFW-AI Service (FastAPI + daemon)** is the real-time security engine. It runs a continuous event loop that consumes DNS queries (from dnsmasq logs, UDP, or journald), tracks network flows via conntrack, scores threats using a multi-layer decision pipeline, and enforces blocking via nftables sets. It also exposes a FastAPI admin interface for managing allow/deny lists, policies, events, users, and audit logs.

---

## Key Features

### Threat Detection and Enforcement
- Multi-layer scoring: DNS domain feeds, TLS SNI inspection, burst detection, flow analysis
- Hard threat gates: PPS saturation, burst flood, bot-like small packet patterns, regular timing detection
- MLP neural network inference for flow-level anomaly detection (scikit-learn)
- YARA rule scanning on domain and SNI payloads
- Automated IP blocking via nftables named sets with configurable timeouts
- Conntrack-based flow tracking with LRU eviction

### Sector Lock System
- Factory-set, immutable sector configuration (school, hospital, government, finance, legal, establishment)
- Sector-specific threshold adjustments, feed lists, and policy overrides
- Hospital mode with IoMT (Internet of Medical Things) high-priority alerting

### Operations Dashboard (Django)
- ASN lookup and configuration
- IP reputation checking
- Alert management with Telegram integration
- Geo-blocking configuration
- JSON schema validation
- Request logging and analytics
- MiniFW policy management (CRUD for allow/deny lists)
- Blocked IP map visualization

### Unified Dashboard Features (Django)
- Security event viewer with DataTables server-side processing and Excel export
- User management with 5-tier RBAC (Super Admin, Admin, Operator, Auditor, Viewer)
- Full audit logging with filtering, statistics, and JSON export
- Sector lock status display

### Resilience
- Graceful degradation: service continues without DNS telemetry (fail-open telemetry, fail-closed security)
- Pluggable DNS backends: file, UDP, journald, or none
- Restart storm prevention via systemd StartLimitBurst
- Deployment state tracking in `/var/log/ritapi/deployment_state.json`

---

## Tech Stack

### RITAPI V-Sentinel (Django)

| Component | Technology |
|-----------|-----------|
| Framework | Django 4.2 with Django REST Framework |
| WSGI Server | Gunicorn 22 |
| Database | PostgreSQL 15 (SQLite in-memory for tests) |
| Cache / Rate Limiter | Redis 7 |
| Template Engine | Django Templates |
| Network Tools | ipwhois, httpx, geoip2 |
| Data / ML | pandas, scikit-learn |
| TLS / Crypto | cryptography, pyOpenSSL |
| Validation | jsonschema |
| Task Queue | Celery (optional) |

### MiniFW-AI Service

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI with Uvicorn |
| AI/ML | scikit-learn (MLP), NumPy, pandas, SciPy |
| Security Scanning | yara-python |
| Authentication | python-jose (JWT), passlib + bcrypt, pyotp (TOTP) |
| Database | SQLAlchemy with SQLite |
| Firewall | nftables, ipset (via subprocess) |
| UI | AdminLTE 3 (Jinja2 templates) |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Reverse Proxy | Nginx |
| Process Manager | systemd |
| DNS Telemetry | dnsmasq (optional) |
| Flow Tracking | Linux conntrack (`/proc/net/nf_conntrack`) |
| CI/CD | GitHub Actions |
| Log Rotation | logrotate |

---

## Project Structure

```
ritapi-v-sentinel/
|-- install.sh                          # Main all-in-one installer (interactive menu)
|-- install_fixed.sh                    # Alternative installer variant
|-- vsentinel-audit.sh                  # Integration audit script (read-only diagnostics)
|-- vm_guide.md                         # VM installation walkthrough
|
|-- .github/
|   `-- workflows/
|       `-- pre-flight-check.yml        # CI: security audit, linting, tests
|
|-- docs/
|   |-- CARA_PAKAI.md                   # Usage guide (Indonesian)
|   |-- DEGRADED_MODE_IMPLEMENTATION.md # Resilience architecture documentation
|   |-- PANDUAN_INSTALASI_LENGKAP.md    # Full installation guide (Indonesian)
|   `-- README_INSTALLER.md            # Installer reference
|
|-- scripts/
|   |-- logrotate.d/                    # Logrotate configuration files
|   |-- minifw_fixed/                   # CRUD fix and permission scripts
|   |-- vsentinel.env.template          # Environment variable template
|   |-- vsentinel.env.example           # Environment variable example
|   |-- vsentinel_selftest.sh           # Post-installation self-test with proof pack
|   |-- vsentinel_runtime_guard.sh      # Runtime guard (ExecStartPre)
|   `-- vsentinel_scope_gate.sh         # Scope gate script
|
|-- projects/
|   |-- ritapi_django/                  # Django Operations Dashboard
|   |   |-- manage.py
|   |   |-- requirements.txt
|   |   |-- ritapi_v_sentinel/          # Django project settings, URLs, WSGI/ASGI
|   |   |-- authentication/             # Login, logout, password change, OpsAuth middleware
|   |   |-- asn/                        # ASN lookup and management
|   |   |-- ip_reputation/              # IP reputation checking
|   |   |-- alert/                      # Alert management and services
|   |   |-- blocking/                   # IP blocking module
|   |   |-- json_schema/                # JSON schema validation
|   |   |-- log_channel/                # Request logging
|   |   |-- minifw/                     # MiniFW CRUD integration for Django
|   |   |-- ml/                         # Machine learning module
|   |   |-- ops/                        # Ops dashboard views
|   |   |   |-- ops_asn/
|   |   |   |-- ops_iprep/
|   |   |   |-- ops_json/
|   |   |   |-- ops_alert/
|   |   |   |-- ops_blocking/
|   |   |   `-- ops_geoblock/
|   |   |-- middlewares/                # Rate limiting, security enforcement
|   |   |-- templates/                  # HTML templates (base, sidebar, dashboards)
|   |   `-- .env                        # Local development environment
|   |
|   `-- minifw_ai_service/             # MiniFW-AI Security Engine
|       |-- requirements.txt
|       |-- app/
|       |   |-- web/                    # FastAPI application
|       |   |   |-- app.py              # FastAPI entrypoint
|       |   |   |-- routers/            # admin, auth, health, status routes
|       |   |   |-- static/             # AdminLTE assets
|       |   |   `-- templates/          # Jinja2 admin templates
|       |   |-- minifw_ai/             # Core security engine
|       |   |   |-- main.py            # Main event loop and scoring logic
|       |   |   |-- policy.py          # Policy configuration loader
|       |   |   |-- enforce.py         # nftables/ipset enforcement
|       |   |   |-- feeds.py           # Domain feed matcher
|       |   |   |-- events.py          # Event model and writer
|       |   |   |-- burst.py           # Burst/rate tracker
|       |   |   |-- collector_dnsmasq.py  # DNS event stream (file/UDP)
|       |   |   |-- collector_zeek.py  # Zeek TLS SNI collector
|       |   |   |-- collector_flow.py  # Conntrack flow tracker
|       |   |   |-- sector_lock.py     # Factory-set sector configuration
|       |   |   |-- sector_config.py   # Sector threshold adjustments
|       |   |   |-- netutil.py         # IP/subnet utilities
|       |   |   `-- utils/
|       |   |       |-- mlp_engine.py  # MLP neural network detector
|       |   |       `-- yara_scanner.py # YARA rule scanner
|       |   |-- controllers/           # Admin and auth controllers
|       |   |-- services/              # Business logic services
|       |   |-- models/                # SQLAlchemy models (User, Audit)
|       |   |-- schemas/               # Pydantic schemas
|       |   |-- middleware/            # Auth middleware (JWT)
|       |   `-- database.py            # SQLAlchemy database initialization
|       |-- config/                     # Policy JSON, feeds, dnsmasq config
|       |-- systemd/                   # minifw-ai.service unit file
|       |-- testing/                   # Integration and unit tests
|       |-- yara_rules/                # YARA rule files
|       |-- models/                    # Trained ML model files
|       `-- scripts/                   # Helper scripts
```

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Ubuntu 20.04 / Debian 11 | Ubuntu 22.04 / Debian 12 |
| RAM | 2 GB | 4 GB |
| Disk | 5 GB free | 10 GB free |
| CPU | 1 vCPU | 2 vCPUs |
| Python | 3.10+ | 3.11+ |
| Network | Internet for package downloads | - |
| Access | Root / sudo | - |

Additional runtime dependencies (installed by the installer):

- PostgreSQL
- Redis
- Nginx
- nftables
- ipset
- dnsmasq (optional -- system operates in degraded mode without it)

---

## Installation

### Automated Installation (Recommended)

The project includes an all-in-one interactive installer:

```bash
chmod +x install.sh
sudo ./install.sh
```

The installer presents an interactive menu:

```
1. Install (Full Installation)
2. Status (Check Services)
3. Uninstall (Remove Everything)
4. Exit
```

The installer will:
1. Detect the web server user (www-data, nginx, or apache)
2. Install all system dependencies (Python, PostgreSQL, Redis, Nginx, nftables, ipset)
3. Create Python virtual environments for both services
4. Install Python dependencies from requirements files
5. Configure Nginx as a reverse proxy
6. Set up systemd service units (`ritapi-gunicorn.service`, `minifw-ai.service`)
7. Run Django migrations and optionally create a superuser
8. Detect DNS telemetry availability and configure degraded mode if needed
9. Write a deployment state file to `/var/log/ritapi/deployment_state.json`

Installation paths:
- Django application: `/opt/ritapi_v_sentinel`
- MiniFW-AI service: `/opt/minifw_ai`
- Unified configuration: `/etc/ritapi/vsentinel.env`
- Logs: `/var/log/ritapi/`

---

## Configuration

### Environment Variables

All configuration is managed through a unified environment file at `/etc/ritapi/vsentinel.env`. A template is provided at `scripts/vsentinel.env.template`.

#### Shared Secrets

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Django cryptographic signing key | (required) |
| `MINIFW_SECRET_KEY` | MiniFW JWT signing secret | (required) |
| `MINIFW_ADMIN_PASSWORD` | Admin bootstrap password for MiniFW | (required) |
| `DB_PASSWORD` | PostgreSQL password | (required) |
| `TELEGRAM_TOKEN` | Telegram bot token for alerts | (empty) |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alerts | (empty) |

#### Django Web

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_DEBUG` | Enable debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `ritapi_v_sentinel` |
| `DB_USER` | PostgreSQL user | `ritapi` |
| `DB_HOST` | PostgreSQL host | `127.0.0.1` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `REDIS_URL` | Redis connection URL | `redis://127.0.0.1:6379/0` |
| `APP_VERSION` | Application version label | `0.1.0` |

#### MiniFW Core

| Variable | Description | Default |
|----------|-------------|---------|
| `MINIFW_POLICY` | Path to policy.json | `/opt/minifw_ai/config/policy.json` |
| `MINIFW_FEEDS` | Path to feeds directory | `/opt/minifw_ai/config/feeds` |
| `MINIFW_LOG` | Path to events log | `/opt/minifw_ai/logs/events.jsonl` |
| `MINIFW_FLOW_RECORDS` | Path to flow records log | `/opt/minifw_ai/logs/flow_records.jsonl` |
| `MINIFW_DNS_SOURCE` | DNS telemetry source: `file`, `udp`, `journald`, `none` | `none` |
| `DEGRADED_MODE` | Degraded telemetry mode flag (`0` or `1`) | `0` |
| `MINIFW_DNS_LOG_PATH` | DNS log path (when source=file) | (empty) |
| `MINIFW_YARA_RULES` | YARA rules directory | `/opt/minifw_ai/yara_rules` |
| `MINIFW_MLP_MODEL` | MLP model file path | `/opt/minifw_ai/models/mlp_v2.joblib` |
| `GAMBLING_ONLY` | Regulatory enforcement mode (must be `1`) | `1` |
| `AI_ENABLED` | Enable/disable AI modules | `true` |
| `MINIFW_MAX_FLOWS` | Maximum tracked flows (LRU) | `20000` |
| `MINIFW_FLOW_FREQ_THRESHOLD` | Flow frequency threshold for hard gate | `200` |

### Policy Configuration

The MiniFW engine reads its policy from a JSON file (default: `/opt/minifw_ai/config/policy.json`). The policy defines:

- **Segments**: Network segments with block and monitor score thresholds
- **Segment Subnets**: CIDR-to-segment mapping
- **Features**: Scoring weights for DNS, SNI, ASN, burst, MLP, and YARA
- **Enforcement**: nftables set name, IP timeout, table, and chain
- **Collectors**: dnsmasq log path, Zeek SSL log path, Zeek SNI toggle
- **Burst**: DNS queries-per-minute thresholds for monitor and block actions

---

## Usage

### Accessing the Dashboard

After installation, access the Django dashboard at:

```
http://<SERVER_IP>/
```

Authenticated superusers are redirected to the ops dashboard. The dashboard provides navigation to all operational modules via a sidebar.

### Creating an Admin User

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data ./venv/bin/python manage.py createsuperuser
```

### Service Management

```bash
# Check status of all services
sudo systemctl status ritapi-gunicorn minifw-ai nginx

# Restart individual services
sudo systemctl restart ritapi-gunicorn
sudo systemctl restart minifw-ai
sudo systemctl restart nginx

# View real-time logs
sudo journalctl -u ritapi-gunicorn -f
sudo journalctl -u minifw-ai -f
```

### Using the Installer Status Check

```bash
sudo ./install.sh status
```

---

## API Endpoints

### Django Application

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect to dashboard or login |
| GET | `/healthz` | Health check endpoint |
| GET | `/admin/` | Django admin interface |
| - | `/auth/login/`, `/auth/logout/` | Authentication |
| - | `/asn/` | ASN lookup and management |
| - | `/ip-reputation/` | IP reputation checking |
| - | `/alerts/` | Alert management |
| - | `/blocking/` | IP blocking management |
| - | `/json/` | JSON schema validation |
| - | `/ops/requestlogs/` | Request log viewer |
| - | `/ops/` | Operations dashboard |
| - | `/ops/minifw/` | MiniFW configuration UI |

### MiniFW-AI Service (FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service status |
| GET | `/health/` | Health check |
| GET | `/status/` | Service status details |
| GET | `/auth/login` | Login page |
| POST | `/auth/login` | Authenticate (returns JWT) |
| GET | `/admin/` | Dashboard |
| GET/POST/PUT/DELETE | `/admin/allow-domain` | Allowed domains CRUD |
| GET/POST/PUT/DELETE | `/admin/deny-ip` | Denied IPs CRUD |
| GET/POST/PUT/DELETE | `/admin/deny-asn` | Denied ASNs CRUD |
| GET/POST/PUT/DELETE | `/admin/deny-domain` | Denied domains CRUD |
| GET | `/admin/events` | Events viewer page |
| GET | `/admin/api/events` | Events DataTables API |
| GET | `/admin/api/events/download` | Events Excel export |
| GET/POST | `/admin/policy` | Policy configuration |
| POST | `/admin/policy/segment` | Add segment |
| DELETE | `/admin/policy/segment/{name}` | Delete segment |
| POST | `/admin/policy/segment/subnets` | Update segment subnets |
| POST | `/admin/policy/features` | Update feature weights |
| POST | `/admin/policy/enforcement` | Update enforcement config |
| POST | `/admin/policy/collectors` | Update collectors config |
| POST | `/admin/policy/burst` | Update burst thresholds |
| GET | `/admin/users` | User management page |
| GET/POST | `/admin/api/users` | List / create users |
| PUT | `/admin/api/users/{id}` | Update user |
| PUT | `/admin/api/users/{id}/password` | Change password |
| DELETE | `/admin/api/users/{id}` | Delete user |
| GET | `/admin/audit-logs` | Audit logs page |
| GET | `/admin/api/audit/logs` | Audit logs API (filterable) |
| GET | `/admin/api/audit/statistics` | Audit statistics |
| GET | `/admin/api/audit/export` | Export audit logs |
| GET | `/admin/api/sector-lock` | Sector lock status |

---

## Testing

### Django Tests

```bash
cd /opt/ritapi_v_sentinel  # or projects/ritapi_django
python manage.py test
```

Tests use an in-memory SQLite database (configured in `settings.py` when `test` is in `sys.argv`).

Existing test directories include:
- `alert/test/` -- Alert models, views, and services
- `asn/test/` -- ASN models, views, and services
- `ip_reputation/test/` -- IP reputation models, views, and services

### MiniFW-AI Tests

```bash
cd projects/minifw_ai_service
pip install pytest pytest-cov pytest-asyncio

# Set required environment variables
export MINIFW_SECRET_KEY=test-secret-key
export MINIFW_ADMIN_PASSWORD=test-admin-pass

pytest testing/ -v
```

Test files include:
- `test_baseline_hard_gates.py` -- Hard threat gate logic
- `test_flow_collector_simulated.py` -- Flow tracking simulation
- `test_full_integration.py` -- End-to-end integration
- `test_mlp_inference.py` / `test_mlp_integration.py` -- MLP model tests
- `test_yara_scanner.py` -- YARA rule scanning
- `test_sector_lock.py` -- Sector lock system
- `test_standalone_integration.py` -- Standalone integration
- Integration scripts for real traffic and flow collection

### CI Pipeline

The GitHub Actions workflow (`.github/workflows/pre-flight-check.yml`) runs on pushes to `main`, `master`, and `develop`, and on pull requests to `main`/`master`. It executes:

1. **Security Audit** -- detect-secrets, pip-audit, Bandit linter, .env file detection
2. **Code Quality** -- flake8, black formatting check, TODO/FIXME scanning
3. **MiniFW-AI Tests** -- pytest with coverage
4. **Django Tests** -- Django migrations and test runner (with PostgreSQL and Redis services)
5. **Pre-Flight Report** -- Consolidated go/no-go verdict

---

## Deployment

### Production Deployment

The installer handles production deployment. Key production considerations:

1. Generate strong secrets:
   ```bash
   openssl rand -hex 32  # Use for DJANGO_SECRET_KEY and MINIFW_SECRET_KEY
   ```

2. Set `DJANGO_DEBUG=False` in `/etc/ritapi/vsentinel.env`

3. Configure `DJANGO_ALLOWED_HOSTS` with your domain/IP

4. Set up HTTPS with Let's Encrypt:
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```

5. Configure firewall:
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

### Systemd Services

After installation, two primary services run:

- `ritapi-gunicorn.service` -- Django application via Gunicorn
- `minifw-ai.service` -- MiniFW-AI security engine

The MiniFW-AI service unit includes:
- Pre-start configuration validation (`config_check.py`)
- Pre-start runtime guard (`vsentinel_runtime_guard.sh`)
- Restart storm prevention (`StartLimitBurst=5`, `StartLimitIntervalSec=300`)
- Automatic restart on failure (`RestartSec=10`)

### Post-Installation Verification

Run the self-test script to verify the installation and generate a regulatory proof pack:

```bash
sudo /opt/ritapi-v-sentinel/scripts/vsentinel_selftest.sh
```

This checks:
- Service status and enablement (ritapi-gunicorn, minifw-ai, nginx)
- Configuration file presence
- GAMBLING_ONLY enforcement flag
- Deployment state and operational mode (FULL or DEGRADED)
- IPset existence

The proof pack is written to `/var/log/ritapi/proof_packs/` as a JSON file.

### Integration Audit

Run the integration audit to detect known mismatches between the Django dashboard and MiniFW-AI:

```bash
sudo ./vsentinel-audit.sh
```

This performs read-only checks on:
- Filesystem layout and expected files
- Systemd unit configuration correctness
- Firewall dependency availability (nft, ipset)
- Policy schema drift
- Dashboard-to-engine privilege boundaries
- DNS/resolver conflicts
- Python dependency compatibility (NumPy, pandas, scikit-learn, SciPy)

---

## Security Features

### Django Middleware Stack

The Django application applies security middleware in this order:

1. **RateLimiterMiddleware** -- Per-IP rate limiting backed by Redis (default: 20 requests per 60 seconds). Returns HTTP 429 on excess. Skips health checks, admin, static assets, and ops paths.

2. **SecurityEnforcementMiddleware** -- Validates JSON request bodies (max 2 MB, content-type enforcement) and inspects file uploads. Configurable path exclusions.

3. **OpsAuthMiddleware** -- Enforces authentication on `/ops/` paths.

### MiniFW-AI Security

- **JWT Authentication** -- All admin endpoints require a valid JWT token
- **TOTP 2FA** -- Optional TOTP-based two-factor authentication via pyotp
- **RBAC** -- Role-based access control for user management (Super Admin required for user CRUD)
- **Password Hashing** -- bcrypt via passlib
- **Input Validation** -- nftables object names validated with strict regex (alphanumeric + underscore, max 32 chars)
- **Audit Logging** -- All administrative actions recorded with timestamps, user, action, severity, and resource type

### Regulatory Compliance

- `GAMBLING_ONLY=1` hard guard: the MiniFW-AI engine refuses to start if this flag is not set
- Sector lock system prevents runtime modification of the deployment sector
- Proof pack generation for regulatory auditing
- Deployment state file tracks telemetry availability

---

## Operational Tooling

| Script | Location | Purpose |
|--------|----------|---------|
| `install.sh` | Root | All-in-one installer with install/status/uninstall menu |
| `vsentinel-audit.sh` | Root | Read-only integration audit (detect mismatches) |
| `vsentinel_selftest.sh` | `scripts/` | Post-install self-test with proof pack generation |
| `vsentinel_runtime_guard.sh` | `scripts/` | ExecStartPre runtime guard for MiniFW-AI |
| `vsentinel_scope_gate.sh` | `scripts/` | Scope gate enforcement |
| `fix_permissions.sh` | `scripts/minifw_fixed/` | Fix CRUD permissions for MiniFW |

### Log Locations

| Log | Path |
|-----|------|
| Django (Gunicorn) | `journalctl -u ritapi-gunicorn` |
| MiniFW-AI | `journalctl -u minifw-ai` |
| Nginx errors | `/var/log/nginx/error.log` |
| MiniFW events | `/opt/minifw_ai/logs/events.jsonl` |
| MiniFW flow records | `/opt/minifw_ai/logs/flow_records.jsonl` |
| Deployment state | `/var/log/ritapi/deployment_state.json` |
| Self-test proof packs | `/var/log/ritapi/proof_packs/` |

### Backup

```bash
sudo tar -czf backup_$(date +%Y%m%d).tar.gz \
    /opt/ritapi_v_sentinel \
    /opt/minifw_ai/config \
    /etc/ritapi/vsentinel.env
```

---

## Troubleshooting

### Services not starting

```bash
# Check detailed service status
sudo systemctl status ritapi-gunicorn
sudo systemctl status minifw-ai

# View recent logs
sudo journalctl -u ritapi-gunicorn -n 100
sudo journalctl -u minifw-ai -n 100

# Check Nginx configuration
sudo nginx -t
```

### MiniFW-AI restart storms

The service unit includes `StartLimitBurst=5` and `StartLimitIntervalSec=300` to prevent restart storms. If the service is flapping:

```bash
# Check restart limits
systemctl show minifw-ai | grep -i limit

# Check for DNS-related failures
journalctl -u minifw-ai --since "1 hour ago" | grep -i "degraded\|error\|fatal"
```

### Permission errors on MiniFW CRUD

```bash
cd scripts/minifw_fixed
sudo ./fix_permissions.sh
```

### Redis connection issues (rate limiter)

The rate limiter middleware fails open -- if Redis is unavailable, requests are allowed through. Check Redis status:

```bash
sudo systemctl status redis
redis-cli ping
```

### Web dashboard not accessible

```bash
sudo systemctl restart ritapi-gunicorn nginx
sudo journalctl -u ritapi-gunicorn -n 50
```

---

## Additional Documentation

| Document | Path | Description |
|----------|------|-------------|
| Quick Start | `QUICKSTART.md` | Three-step installation guide |
| Resilience Reference | `RESILIENCE_QUICKSTART.md` | Degraded mode implementation details |
| VM Guide | `vm_guide.md` | Full VM installation walkthrough |
| Usage Guide | `docs/CARA_PAKAI.md` | Step-by-step usage guide (Indonesian) |
| Full Install Guide | `docs/PANDUAN_INSTALASI_LENGKAP.md` | Detailed installation documentation (Indonesian) |
| Degraded Mode | `docs/DEGRADED_MODE_IMPLEMENTATION.md` | Resilience architecture deep dive |
| Installer Reference | `docs/README_INSTALLER.md` | Installer quick reference |

---

## License

As per original projects.

---

**Version:** 2.0 (All-in-One Complete Package)
