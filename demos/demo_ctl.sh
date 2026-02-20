#!/bin/bash
# RITAPI Sentinel - Demo Controller
# Usage: ./demos/demo_ctl.sh {seed|reset}

# Resolve paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DJANGO_DIR="$PROJECT_ROOT/projects/ritapi_django"
PYTHON_DEMO="$SCRIPT_DIR/demo_ritapi_dashboard.py"

# 1. Automatic Venv Detection
if [ -f "$DJANGO_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$DJANGO_DIR/venv/bin/python"
elif [ -f "/opt/ritapi_v_sentinel/venv/bin/python" ]; then
    VENV_PYTHON="/opt/ritapi_v_sentinel/venv/bin/python"
elif [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    VENV_PYTHON="python3"
else
    echo "Error: Python 3 not found. Please ensure python3 is installed."
    exit 1
fi

# 2. Set Demo Environment Variables
# These defaults ensure the script works even if /etc/ritapi/vsentinel.env is missing
export DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-"demo-secret-key-12345"}
export DATABASE_URL=${DATABASE_URL:-"sqlite:///$DJANGO_DIR/demo_db.sqlite3"}
export DJANGO_SETTINGS_MODULE="ritapi_v_sentinel.settings"

case "$1" in
    seed)
        echo ">>> SEEDING RITAPI DEMO DATA..."
        $VENV_PYTHON "$PYTHON_DEMO"
        echo ">>> Done. Dashboard: http://157.66.9.210/ops/"
        echo ">>> Credentials: admin / admin123"
        ;;
    reset)
        echo ">>> RESETTING RITAPI DEMO DATA..."
        $VENV_PYTHON "$PYTHON_DEMO" --reset
        echo ">>> Done. Database is now clean."
        ;;
    *)
        echo "Usage: $0 {seed|reset}"
        echo "  seed  - Populate dashboard with sample alerts, logs, and events"
        echo "  reset - Clear all demo data for a fresh start"
        exit 1
        ;;
esac
