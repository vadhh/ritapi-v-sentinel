#!/bin/bash
# RITAPI Sentinel - Demo Controller
# Usage: ./demos/demo_ctl.sh {seed|reset}

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Resolve paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_DEMO="$SCRIPT_DIR/demo_ritapi_dashboard.py"

# Production Detection
PRODUCTION_ROOT="/opt/ritapi_v_sentinel"
if [ -d "$PRODUCTION_ROOT" ]; then
    VENV_PYTHON="$PRODUCTION_ROOT/venv/bin/python"
    DJANGO_DIR="$PRODUCTION_ROOT"
elif [ -f "$PROJECT_ROOT/projects/ritapi_django/venv/bin/python" ]; then
    VENV_PYTHON="$PROJECT_ROOT/projects/ritapi_django/venv/bin/python"
    DJANGO_DIR="$PROJECT_ROOT/projects/ritapi_django"
elif [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
    DJANGO_DIR="$PROJECT_ROOT/projects/ritapi_django"
else
    VENV_PYTHON="python3"
    DJANGO_DIR="$PROJECT_ROOT/projects/ritapi_django"
fi

# Set working directory for Django environment
cd "$DJANGO_DIR"

case "$1" in
    seed)
        echo -e "${BLUE}>>> INJECTING RITAPI DEMO DATA...${NC}"
        $VENV_PYTHON "$PYTHON_DEMO"
        ;;
    reset)
        echo -e "${RED}>>> REMOVING RITAPI DEMO DATA...${NC}"
        $VENV_PYTHON "$PYTHON_DEMO" --reset
        ;;
    *)
        echo "Usage: $0 {seed|reset}"
        echo "  seed  - Inject realistic sample data into existing database"
        echo "  reset - Wipe sample logs/alerts for a fresh start"
        exit 1
        ;;
esac
