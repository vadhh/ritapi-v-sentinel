# MiniFW-AI Project Context

## Overview
**MiniFW-AI** is a gateway metadata protection layer designed for RitAPI-AI V-Sentinel. It operates as a client-installed firewall that analyzes network traffic metadata (DNS, TLS SNI) to detect and block threats without requiring TLS inspection (MITM) or browser proxies.

It features a hybrid detection engine:
1.  **Rule-based:** Policy enforcement based on DNS/SNI feeds.
2.  **Behavioral:** Burst detection for high-rate traffic.
3.  **AI/ML:** An MLP (Multi-Layer Perceptron) engine that scores traffic flows based on 24 extracted features.
4.  **Content-based:** YARA scanning for traffic patterns.

## Architecture

### Core Components
*   **Collector (`app/minifw_ai/collector_*.py`):**
    *   **DNS:** Tails `dnsmasq` logs to capture DNS queries.
    *   **Zeek (Optional):** Tails Zeek SSL logs for TLS SNI visibility.
    *   **Flow:** Tracks network flows (5-tuple) and extracts features for the AI engine.
*   **Logic Engine (`app/minifw_ai/main.py`):**
    *   Central event loop.
    *   Aggregates signals (Blocklists, Burst, AI Score).
    *   Calculates a final "threat score" (0-100).
*   **AI Engine (`app/minifw_ai/utils/mlp_engine.py`):**
    *   Uses `scikit-learn` MLPClassifier.
    *   Analyzes flow features (duration, packet sizes, inter-arrival times, etc.).
*   **Enforcement (`app/minifw_ai/enforce.py`):**
    *   **Mechanism:** `nftables` + `ipset`.
    *   **Action:** Adds blocking IPs to the `minifw_block_v4` ipset with a timeout.
*   **Sector Lock (`app/minifw_ai/sector_lock.py`):**
    *   Ensures immutable, factory-set configurations for specific industries (e.g., Hospital, School).
*   **Web Interface (`app/web/app.py`):**
    *   **Framework:** FastAPI.
    *   **Purpose:** Admin dashboard, policy management, audit logs, and user management.

### Directory Structure
*   `app/minifw_ai/`: Core application logic (engines, collectors, enforcement).
*   `app/web/`: FastAPI web application, routers, and static assets.
*   `app/controllers/`: MVC-style controllers for handling web requests.
*   `app/services/`: Business logic layer (Auth, Policy, User Management).
*   `app/models/`: SQLAlchemy database models (User, Audit).
*   `config/`: Configuration files (`policy.json`, `sector_lock.json`) and threat feeds (`feeds/*.txt`).
*   `scripts/`: Utility scripts for installation, training, and simulation.
*   `testing/`: Integration and unit tests (`pytest`).
*   `models/`: Serialized ML models (`mlp_engine.pkl`).
*   `yara_rules/`: Custom YARA rules for traffic analysis.

## Key Technologies
*   **Language:** Python 3.x
*   **Web Framework:** FastAPI + Jinja2 + AdminLTE
*   **Database:** SQLAlchemy (SQLite by default)
*   **System Tools:** `dnsmasq`, `nftables`, `ipset`, `zeek` (optional)
*   **ML Libraries:** `scikit-learn`, `pandas`, `numpy`
*   **Security:** JWT (jose), Passlib (bcrypt), PyOTP (TOTP)

## Development & Usage

### Installation
The project is designed to run on Linux (Debian/Ubuntu) as a gateway.
```bash
sudo ./scripts/install.sh
```
*   Installs dependencies (system & python venv).
*   Deploys code to `/opt/minifw_ai`.

### Running the Service
```bash
sudo ./scripts/install_systemd.sh
sudo systemctl start minifw-ai
```

### Manual Execution (Dev)
```bash
# Set required env vars if not using defaults
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m app.minifw_ai.main
```

### AI Model Training
To train the MLP engine with new flow data:
```bash
python3 scripts/train_mlp.py --data data/testing_output/flow_records_labeled.csv --output models/mlp_engine.pkl
```

### Testing
Tests are located in `testing/`.
```bash
pytest testing/
```

## Conventions
*   **Type Hinting:** Extensive use of Python type hints.
*   **Configuration:** Environment variables override default paths (e.g., `MINIFW_POLICY`, `MINIFW_LOG`).
*   **Logging:** JSONL format for machine-readable event logs (`events.jsonl`) and database audit logs.
*   **MVC Pattern:** Separation of concerns via Routers -> Controllers -> Services -> Models.

## Critical Files
*   `app/minifw_ai/main.py`: The "brain" of the firewall.
*   `app/web/app.py`: FastAPI entry point.
*   `app/middleware/auth_middleware.py`: Authentication and authorization logic.
*   `config/policy.json`: Defines scoring weights and thresholds.
*   `requirements.txt`: Python dependencies.