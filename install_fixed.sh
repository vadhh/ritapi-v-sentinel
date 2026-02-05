#!/bin/bash

################################################################################
# RITAPI V-Sentinel & MiniFW-AI - Complete Installer Package
# 
# Installer all-in-one untuk instalasi lengkap:
# 1. RITAPI V-Sentinel (Django Web Application)
# 2. MiniFW-AI (Backend Security Service)
#
# Version: 2.0 (All-in-One Package)
################################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
DJANGO_PROJECT_DIR="/opt/ritapi_v_sentinel"
MINIFW_AI_DIR="/opt/minifw_ai"
DJANGO_USER="www-data"
DJANGO_GROUP="www-data"

# Source directories (from package)
DJANGO_SOURCE="$SCRIPT_DIR/projects/ritapi_django"
MINIFW_SOURCE="$SCRIPT_DIR/projects/minifw_ai_service"

################################################################################
# Header
################################################################################

show_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║   RITAPI V-Sentinel & MiniFW-AI Complete Installer           ║"
    echo "║   All-in-One Package - Version 2.0                           ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

# Run Django manage.py with env loaded from /etc/ritapi/vsentinel.env
# Why: settings.py reads os.environ (django-environ), so manage.py MUST run with those vars set.
# Important: sudo resets env by default, so we source the env file inside a shell running as $DJANGO_USER.
run_django_with_env() {
    local envfile="/etc/ritapi/vsentinel.env"
    local py="$DJANGO_PROJECT_DIR/venv/bin/python"
    local manage="$DJANGO_PROJECT_DIR/manage.py"

    if [ ! -f "$envfile" ]; then
        print_error "Missing $envfile (environment is required for Django)"
        return 1
    fi

    # IMPORTANT:
    # We expand $envfile/$DJANGO_PROJECT_DIR/$py/$manage in the *outer* shell so the inner bash
    # receives literal paths. Using single quotes inside the bash -lc string would prevent expansion
    # and would try to source a file literally named '$envfile' (bug).
    sudo -u "$DJANGO_USER" bash -lc "set -euo pipefail
        set -a
        . \"${envfile}\"
        set +a
        cd \"${DJANGO_PROJECT_DIR}\"
        exec \"${py}\" \"${manage}\" \"\$@\"
    " -- "$@"
}

ensure_static_root_setting() {
    # Django collectstatic requires STATIC_ROOT to be set to a real filesystem path.
    # This project ships without STATIC_ROOT in settings.py, so collectstatic fails.
    # We align STATIC_ROOT with the directory we already create and serve via nginx (/opt/ritapi_v_sentinel/static).
    local settings_file="$DJANGO_PROJECT_DIR/ritapi_v_sentinel/settings.py"
    if [ ! -f "$settings_file" ]; then
        print_warning "settings.py not found at $settings_file (skipping STATIC_ROOT patch)"
        return 0
    fi

    if grep -qE '^\s*STATIC_ROOT\s*=' "$settings_file"; then
        return 0
    fi

    # Append at end to avoid fighting existing config.
    cat >>"$settings_file" <<'PYEOF'

# --- Installer patch: required for collectstatic ---
# collectstatic needs STATIC_ROOT; align with nginx alias (/opt/ritapi_v_sentinel/static/)
import os
STATIC_ROOT = os.environ.get("STATIC_ROOT", os.path.join(BASE_DIR, "static"))
PYEOF
    print_success "Patched settings.py with STATIC_ROOT (for collectstatic)"
    return 0
}
# --- Admin creation (NEVER abort install) ---
create_admin_maybe() {
    local py="$DJANGO_PROJECT_DIR/venv/bin/python"
    local manage="$DJANGO_PROJECT_DIR/manage.py"

    echo "[STEP] Django admin creation (optional)"

    # Optional non-interactive creation via env vars
    if [[ -n "$DJANGO_SUPERUSER_USERNAME" || -n "$DJANGO_SUPERUSER_EMAIL" || -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
        if [[ -z "$DJANGO_SUPERUSER_USERNAME" || -z "$DJANGO_SUPERUSER_EMAIL" || -z "$DJANGO_SUPERUSER_PASSWORD" ]]; then
            echo "[WARN] Incomplete DJANGO_SUPERUSER_* env vars. Skipping non-interactive creation."
        else
            if ! (run_django_with_env createsuperuser --noinput); then
                echo "[WARN] createsuperuser (non-interactive) failed (non-fatal)."
                echo "       You can retry later:"
                echo "       cd $DJANGO_PROJECT_DIR && sudo -u $DJANGO_USER $py $manage createsuperuser"
            fi
            return 0
        fi
    fi

    # If no TTY (common on remote installs / automation), do not attempt interactive prompt.
    if [[ ! -t 0 || ! -t 1 ]]; then
        echo "[WARN] No TTY detected. Skipping interactive createsuperuser."
        echo "       Run later:"
        echo "       cd $DJANGO_PROJECT_DIR && sudo -u $DJANGO_USER $py $manage createsuperuser"
        return 0
    fi

    # Interactive attempt, but do NOT let failure cancel install
    if ! (run_django_with_env createsuperuser); then
        echo "[WARN] createsuperuser failed (non-fatal)."
        echo "       You can retry later:"
        echo "       cd $DJANGO_PROJECT_DIR && sudo -u $DJANGO_USER $py $manage createsuperuser"
    fi

    return 0
}

ensure_firewall_deps() {
    print_header "Installing Firewall Dependencies"

    print_step "Installing firewall deps..."
    apt-get update -y
    apt-get install -y nftables ipset

    if ! command -v nft >/dev/null 2>&1 && [[ ! -x /usr/sbin/nft ]]; then
        print_error "nft not installed correctly"
        exit 1
    fi
    if ! command -v ipset >/dev/null 2>&1 && [[ ! -x /usr/sbin/ipset ]]; then
        print_error "ipset not installed correctly"
        exit 1
    fi

    print_success "Firewall dependencies verified"
}

install_minifw_systemd() {
    print_step "Installing systemd unit: minifw-ai"

    cat >/etc/systemd/system/minifw-ai.service <<'EOF'
[Unit]
Description=MiniFW-AI Security Service
After=network.target dnsmasq.service
Wants=dnsmasq.service
StartLimitIntervalSec=120
StartLimitBurst=5

[Service]
Type=simple
User=root
WorkingDirectory=/opt/minifw_ai

# Critical: systemd default PATH may exclude /usr/sbin; nft/ipset often live there.
Environment="PATH=/usr/sbin:/usr/bin:/sbin:/bin:/opt/minifw_ai/venv/bin"

# Critical: code lives under /opt/minifw_ai/app; python -m needs PYTHONPATH.
Environment="PYTHONPATH=/opt/minifw_ai/app"

Environment="MINIFW_POLICY=/opt/minifw_ai/config/policy.json"
Environment="MINIFW_FEEDS=/opt/minifw_ai/config/feeds"
EnvironmentFile=/etc/ritapi/vsentinel.env

Environment="MINIFW_LOG=/opt/minifw_ai/logs/events.jsonl"

ExecStart=/opt/minifw_ai/venv/bin/python -m minifw_ai
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable minifw-ai
}

ensure_allowed_hosts() {
    local env_file="/etc/ritapi/vsentinel.env"

    local ip
    ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
    [[ -z "$ip" ]] && ip="$(hostname -I 2>/dev/null | awk '{print $1}')"

    if [[ -z "$ip" ]]; then
        print_warning "Could not auto-detect server IP. Leaving ALLOWED_HOSTS unchanged."
        return 0
    fi

    [[ -f "$env_file" ]] || touch "$env_file"

    if grep -q '^ALLOWED_HOSTS=' "$env_file"; then
        if ! grep -q "$ip" "$env_file"; then
            sed -i "s/^ALLOWED_HOSTS=\(.*\)$/ALLOWED_HOSTS=\1,$ip/" "$env_file"
        fi
    else
        echo "ALLOWED_HOSTS=localhost,127.0.0.1,$ip" >>"$env_file"
    fi

    print_success "ALLOWED_HOSTS updated with $ip"
}

post_install_verify() {
    print_header "Post-install verification"

    systemctl is-active --quiet nginx || { print_error "nginx not active"; exit 1; }
    systemctl is-active --quiet ritapi-gunicorn || { print_error "ritapi-gunicorn not active"; exit 1; }
    systemctl is-active --quiet minifw-ai || { print_error "minifw-ai not active"; exit 1; }

    /opt/minifw_ai/venv/bin/python -c 'import shutil; import sys; sys.exit(0 if shutil.which("nft") else 1)' \
        || { print_error "nft not in runtime PATH"; exit 1; }

    curl -fsS http://127.0.0.1:8000/ >/dev/null || print_warning "Gunicorn not serving on 127.0.0.1:8000"

    print_success "Verification complete"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Script ini harus dijalankan sebagai root (gunakan sudo)"
        exit 1
    fi
}

verify_package_structure() {
    print_header "Verifying Package Structure"
    
    local all_good=true
    
    # Check Django project
    if [ -d "$DJANGO_SOURCE" ]; then
        print_success "Django project found: $DJANGO_SOURCE"
    else
        print_error "Django project NOT found: $DJANGO_SOURCE"
        all_good=false
    fi
    
    # Check MiniFW-AI service
    if [ -d "$MINIFW_SOURCE" ]; then
        print_success "MiniFW-AI service found: $MINIFW_SOURCE"
    else
        print_error "MiniFW-AI service NOT found: $MINIFW_SOURCE"
        all_good=false
    fi
    
    # Check for manage.py in Django project
    if [ -f "$DJANGO_SOURCE/manage.py" ]; then
        print_success "Django manage.py found"
    else
        print_error "Django manage.py NOT found"
        all_good=false
    fi
    
    if [ "$all_good" = false ]; then
        echo ""
        print_error "Package structure incomplete!"
        print_info "Expected structure:"
        echo "  installer_package/"
        echo "  ├── install.sh (this script)"
        echo "  ├── projects/"
        echo "  │   ├── ritapi_django/"
        echo "  │   │   └── manage.py"
        echo "  │   └── minifw_ai_service/"
        echo "  └── scripts/"
        exit 1
    fi
    
    print_success "Package structure verified!"
}

detect_web_user() {
    print_step "Detecting web server user..."
    
    if id "www-data" &>/dev/null; then
        DJANGO_USER="www-data"
        DJANGO_GROUP="www-data"
    elif id "nginx" &>/dev/null; then
        DJANGO_USER="nginx"
        DJANGO_GROUP="nginx"
    elif id "apache" &>/dev/null; then
        DJANGO_USER="apache"
        DJANGO_GROUP="apache"
    else
        print_warning "Could not detect web server user"
        read -p "Enter Django user (default: www-data): " custom_user
        DJANGO_USER=${custom_user:-www-data}
        
        # Create user if doesn't exist
        if ! id "$DJANGO_USER" &>/dev/null; then
            print_step "Creating user $DJANGO_USER..."
            useradd -r -s /bin/false "$DJANGO_USER" || true
        fi
        DJANGO_GROUP=$DJANGO_USER
    fi
    
    print_success "Using Django user: $DJANGO_USER:$DJANGO_GROUP"
}

################################################################################
# Installation Functions
################################################################################

install_system_dependencies() {
    print_header "Installing System Dependencies"
    
    print_step "Updating package list..."
    apt-get update -qq
    
    print_step "Installing required packages..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        libpq-dev \
        redis-server \
        nftables \
        ipset \
        sqlite3 \
        git \
        curl \
        wget \
        nginx \
        postgresql \
        postgresql-contrib \
        > /dev/null 2>&1
    
    print_success "System dependencies installed"
}


setup_postgres() {
    print_header "Configuring PostgreSQL for RitAPI"

    local envfile="/etc/ritapi/vsentinel.env"
    if [ ! -f "$envfile" ]; then
        print_error "Missing $envfile; cannot configure DB"
        exit 1
    fi

    # Load env (export) for this installer process
    set -a
    # shellcheck disable=SC1090
    . "$envfile"
    set +a

    # Sanity: required vars
    for v in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
        if [ -z "${!v:-}" ]; then
            print_error "Missing $v in $envfile"
            exit 1
        fi
    done

    systemctl enable postgresql >/dev/null 2>&1 || true
    systemctl start postgresql >/dev/null 2>&1 || true

    # If postgres role already exists from a previous run, our old installer wouldn't update its password.
    # That causes Django migrations to fail with "password authentication failed".
    # Fix: idempotently ensure role exists AND always set password to match $DB_PASSWORD.
    #
    # SECURITY NOTE:
    # Use format('%L', ...) to safely quote the password literal (handles quotes safely).
    sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL >/dev/null
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        EXECUTE format('CREATE ROLE %I LOGIN', '${DB_USER}');
    END IF;

    -- Always sync password to current env (fixes reruns)
    EXECUTE format('ALTER ROLE %I WITH PASSWORD %L', '${DB_USER}', '${DB_PASSWORD}');

    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}') THEN
        EXECUTE format('CREATE DATABASE %I OWNER %I', '${DB_NAME}', '${DB_USER}');
    ELSE
        EXECUTE format('ALTER DATABASE %I OWNER TO %I', '${DB_NAME}', '${DB_USER}');
    END IF;
END
\$\$;
SQL

    # We assume local postgres for default config. If DB_HOST is not local, skip local tuning.
    if [[ "${DB_HOST}" != "localhost" && "${DB_HOST}" != "127.0.0.1" ]]; then
        print_warning "DB_HOST is not local (${DB_HOST}); skipping local postgres tuning."
    fi

    print_success "PostgreSQL configured (db=${DB_NAME}, user=${DB_USER})"
}


install_ritapi_django() {
    print_header "Installing RITAPI V-Sentinel (Django Application)"
    
    # Create project directory
    print_step "Creating Django project directory..."
    mkdir -p "$DJANGO_PROJECT_DIR"
    
    # Copy Django project files
    print_step "Copying Django application files..."
    cp -r "$DJANGO_SOURCE"/* "$DJANGO_PROJECT_DIR/"
    
    # Create virtual environment
    print_step "Creating Python virtual environment..."
    python3 -m venv "$DJANGO_PROJECT_DIR/venv"
    
    # Install Python dependencies
    print_step "Installing Python dependencies..."
    "$DJANGO_PROJECT_DIR/venv/bin/pip" install --upgrade pip -q
    if [ -f "$DJANGO_PROJECT_DIR/requirements.txt" ]; then
        "$DJANGO_PROJECT_DIR/venv/bin/pip" install -r "$DJANGO_PROJECT_DIR/requirements.txt" -q
    fi
    
    # Install gunicorn
    print_step "Installing Gunicorn..."
    "$DJANGO_PROJECT_DIR/venv/bin/pip" install gunicorn -q
    
    # Create necessary directories
    print_step "Creating Django directories..."
    mkdir -p "$DJANGO_PROJECT_DIR/static"
    mkdir -p "$DJANGO_PROJECT_DIR/media"
    mkdir -p "$DJANGO_PROJECT_DIR/logs"
    
    # Set permissions
    print_step "Setting permissions..."
    chown -R "$DJANGO_USER:$DJANGO_GROUP" "$DJANGO_PROJECT_DIR"
    chmod -R 755 "$DJANGO_PROJECT_DIR"
print_step "Setting permissions..."
    chown -R "$DJANGO_USER:$DJANGO_GROUP" "$DJANGO_PROJECT_DIR"
    chmod -R 755 "$DJANGO_PROJECT_DIR"

    # Ensure STATIC_ROOT exists in settings before running collectstatic
    ensure_static_root_setting
    
    # Run migrations
    print_step "Running Django migrations..."
    run_django_with_env migrate --noinput
    
    # Collect static files
    print_step "Collecting static files..."
    run_django_with_env collectstatic --noinput
    
    print_success "RITAPI V-Sentinel installed successfully"
}

install_minifw_ai() {
    print_header "Installing MiniFW-AI (Security Service)"
    
    # Copy MiniFW-AI files
    print_step "Copying MiniFW-AI files..."
    mkdir -p "$MINIFW_AI_DIR"
    
    # Detect structure MiniFW-AI (bisa berbeda)
    if [ -d "$MINIFW_SOURCE/app" ]; then
        # Structure dengan app/ directory
        cp -r "$MINIFW_SOURCE"/* "$MINIFW_AI_DIR/"
    else
        # Structure langsung
        cp -r "$MINIFW_SOURCE"/* "$MINIFW_AI_DIR/"
    fi
    
    # Create virtual environment
    print_step "Creating Python virtual environment for MiniFW-AI..."
    python3 -m venv "$MINIFW_AI_DIR/venv"
    
    # Install dependencies
    print_step "Installing MiniFW-AI dependencies..."
    "$MINIFW_AI_DIR/venv/bin/pip" install --upgrade pip -q
    if [ -f "$MINIFW_AI_DIR/requirements.txt" ]; then
        "$MINIFW_AI_DIR/venv/bin/pip" install -r "$MINIFW_AI_DIR/requirements.txt" -q
    fi
    
    # Create necessary directories
    print_step "Creating MiniFW-AI directories..."
    mkdir -p "$MINIFW_AI_DIR/config/feeds"
    mkdir -p "$MINIFW_AI_DIR/logs"
    
    # Create default configuration
    print_step "Creating default configuration..."
    if [ ! -f "$MINIFW_AI_DIR/config/policy.json" ]; then
        cat > "$MINIFW_AI_DIR/config/policy.json" << 'EOF'
{
  "segments": {
    "critical": {
      "block_threshold": 80,
      "monitor_threshold": 60
    },
    "production": {
      "block_threshold": 75,
      "monitor_threshold": 50
    },
    "staging": {
      "block_threshold": 85,
      "monitor_threshold": 65
    },
    "default": {
      "block_threshold": 70,
      "monitor_threshold": 45
    }
  },
  "segment_subnets": {
    "critical": [],
    "production": [],
    "staging": [],
    "default": []
  },
  "features": {
    "dns_weight": 40,
    "sni_weight": 35,
    "asn_weight": 15,
    "burst_weight": 10
  },
  "enforcement": {
    "enabled": true,
    "ipset_name_v4": "minifw_block_v4",
    "ip_timeout_seconds": 86400
  },
  "burst": {
    "window_seconds": 10,
    "threshold": 100
  }
}
EOF
    fi
    
    # Create feed files
    print_step "Creating feed files..."
    for feed in allow_domains deny_domains deny_ips deny_asn; do
        if [ ! -f "$MINIFW_AI_DIR/config/feeds/${feed}.txt" ]; then
            cat > "$MINIFW_AI_DIR/config/feeds/${feed}.txt" << EOF
# MiniFW-AI Feed: ${feed}
# Add one entry per line
EOF
        fi
    done
    
    # Set permissions
    print_step "Setting MiniFW-AI permissions..."
    # Keep runtime code owned by root (service runs as root), but allow dashboard (www-data) to edit config.
    chown -R root:root "$MINIFW_AI_DIR"
    chown -R "$DJANGO_USER:$DJANGO_GROUP" "$MINIFW_AI_DIR/config" "$MINIFW_AI_DIR/logs" 2>/dev/null || true
    chmod -R 755 "$MINIFW_AI_DIR"
    find "$MINIFW_AI_DIR/config" -type f -exec chmod 644 {} \;
    
    # Create ipset
    print_step "Creating ipset for blocking..."
    ipset create minifw_block_v4 hash:ip timeout 86400 -exist 2>/dev/null || true
    
    # Install systemd service
    print_step "Installing MiniFW-AI systemd service..."
    install_minifw_systemd
    
    print_success "MiniFW-AI installed successfully"
}

install_gunicorn_service() {
    print_header "Installing Gunicorn Service for Django"
    
    print_step "Creating Gunicorn systemd service..."
    cat > /etc/systemd/system/ritapi-gunicorn.service << EOF
[Unit]
Description=RITAPI V-Sentinel Gunicorn Service
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=$DJANGO_USER
Group=$DJANGO_GROUP
WorkingDirectory=$DJANGO_PROJECT_DIR

# Single source of truth for runtime config
EnvironmentFile=/etc/ritapi/vsentinel.env
Environment="PATH=$DJANGO_PROJECT_DIR/venv/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="DJANGO_SETTINGS_MODULE=ritapi_v_sentinel.settings"

ExecStart=$DJANGO_PROJECT_DIR/venv/bin/gunicorn \
    --config /dev/null \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile $DJANGO_PROJECT_DIR/logs/gunicorn-access.log \
    --error-logfile $DJANGO_PROJECT_DIR/logs/gunicorn-error.log \
    ritapi_v_sentinel.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ritapi-gunicorn 2>/dev/null || true
    
    print_success "Gunicorn service installed"
}

configure_nginx() {
    print_header "Configuring Nginx"
    
    print_step "Creating Nginx configuration..."
    cat > /etc/nginx/sites-available/ritapi << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location /static/ {
        alias /opt/ritapi_v_sentinel/static/;
    }

    location /media/ {
        alias /opt/ritapi_v_sentinel/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF
    
    # Enable site
    ln -sf /etc/nginx/sites-available/ritapi /etc/nginx/sites-enabled/ 2>/dev/null || true
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    
    # Test nginx configuration
    print_step "Testing Nginx configuration..."
    nginx -t 2>/dev/null || print_warning "Nginx config test had warnings (may be OK)"
    
    systemctl enable nginx 2>/dev/null || true
    
    print_success "Nginx configured"
}

apply_minifw_crud_fix() {
    print_header "Applying MiniFW CRUD Fixes"
    
    if [ -d "$SCRIPT_DIR/scripts/minifw_fixed" ]; then
        print_step "Copying fixed MiniFW files..."
        
        # Copy fixed Python files
        if [ -f "$SCRIPT_DIR/scripts/minifw_fixed/minifw/services.py" ]; then
            cp "$SCRIPT_DIR/scripts/minifw_fixed/minifw/services.py" "$DJANGO_PROJECT_DIR/minifw/"
            print_success "Updated minifw/services.py"
        fi
        
        if [ -f "$SCRIPT_DIR/scripts/minifw_fixed/minifw/views.py" ]; then
            cp "$SCRIPT_DIR/scripts/minifw_fixed/minifw/views.py" "$DJANGO_PROJECT_DIR/minifw/"
            print_success "Updated minifw/views.py"
        fi
        
        # Copy fixed templates
        if [ -d "$SCRIPT_DIR/scripts/minifw_fixed/templates" ]; then
            cp -r "$SCRIPT_DIR/scripts/minifw_fixed/templates/ops_template/minifw_config"/* \
                "$DJANGO_PROJECT_DIR/templates/ops_template/minifw_config/" 2>/dev/null || true
            print_success "Updated MiniFW templates"
        fi
        
        print_success "MiniFW CRUD fixes applied"
    else
        print_warning "MiniFW CRUD fix not found, skipping"
    fi
}

create_admin_user() {
    print_header "Django Admin User Setup"
    
    echo ""
    print_info "Anda dapat membuat Django admin user sekarang atau nanti"
    if [[ ! -t 0 || ! -t 1 ]]; then
        create_admin_maybe
        return 0
    fi

    read -p "Buat admin user sekarang? (y/N): " create_admin
    
    if [[ "$create_admin" =~ ^[Yy]$ ]]; then
        create_admin_maybe
    else
        print_info "Dilewati. Anda bisa membuat admin user nanti dengan:"
        print_info "cd $DJANGO_PROJECT_DIR && sudo -u $DJANGO_USER ./venv/bin/python manage.py createsuperuser"
    fi
}

start_services() {
    print_header "Starting Services"
    
    print_step "Starting Redis..."
    systemctl start redis-server 2>/dev/null || true
    
    print_step "Starting MiniFW-AI..."
    systemctl start minifw-ai 2>/dev/null || true
    
    print_step "Starting Gunicorn..."
    systemctl start ritapi-gunicorn 2>/dev/null || true
    
    print_step "Starting Nginx..."
    systemctl restart nginx 2>/dev/null || true
    
    sleep 3
    
    print_success "All services started"
}

show_status() {
    print_header "Service Status"
    
    echo ""
    echo -e "${CYAN}Redis:${NC}"
    systemctl status redis-server --no-pager -l 2>/dev/null | head -3 || echo "Not running"
    
    echo ""
    echo -e "${CYAN}MiniFW-AI:${NC}"
    systemctl status minifw-ai --no-pager -l 2>/dev/null | head -3 || echo "Not running"
    
    echo ""
    echo -e "${CYAN}Gunicorn (Django):${NC}"
    systemctl status ritapi-gunicorn --no-pager -l 2>/dev/null | head -3 || echo "Not running"
    
    echo ""
    echo -e "${CYAN}Nginx:${NC}"
    systemctl status nginx --no-pager -l 2>/dev/null | head -3 || echo "Not running"
    echo ""
}

show_completion_message() {
    clear
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║              🎉 INSTALASI BERHASIL! 🎉                       ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Installation Summary${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}✓${NC} RITAPI V-Sentinel: ${YELLOW}$DJANGO_PROJECT_DIR${NC}"
    echo -e "${GREEN}✓${NC} MiniFW-AI Service: ${YELLOW}$MINIFW_AI_DIR${NC}"
    echo -e "${GREEN}✓${NC} Gunicorn Service: ${YELLOW}systemctl status ritapi-gunicorn${NC}"
    echo -e "${GREEN}✓${NC} MiniFW-AI Service: ${YELLOW}systemctl status minifw-ai${NC}"
    echo -e "${GREEN}✓${NC} Nginx Web Server: ${YELLOW}systemctl status nginx${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Akses Aplikasi${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Get IP address
    IP_ADDR=$(hostname -I | awk '{print $1}')
    
    echo -e "${GREEN}🌐 Web Dashboard:${NC}"
    echo "   http://$IP_ADDR/"
    echo "   http://localhost/ (jika di mesin lokal)"
    echo ""
    echo -e "${GREEN}🔐 Login Page:${NC}"
    echo "   http://$IP_ADDR/auth/login/"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Perintah Berguna${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Membuat admin user (jika dilewati):"
    echo "  ${YELLOW}cd $DJANGO_PROJECT_DIR${NC}"
    echo "  ${YELLOW}sudo -u $DJANGO_USER ./venv/bin/python manage.py createsuperuser${NC}"
    echo ""
    echo "Melihat logs:"
    echo "  ${YELLOW}sudo journalctl -u ritapi-gunicorn -f${NC}    # Django logs"
    echo "  ${YELLOW}sudo journalctl -u minifw-ai -f${NC}          # MiniFW-AI logs"
    echo "  ${YELLOW}sudo tail -f /var/log/nginx/error.log${NC}    # Nginx logs"
    echo ""
    echo "Restart services:"
    echo "  ${YELLOW}sudo systemctl restart ritapi-gunicorn${NC}   # Django"
    echo "  ${YELLOW}sudo systemctl restart minifw-ai${NC}         # MiniFW-AI"
    echo "  ${YELLOW}sudo systemctl restart nginx${NC}             # Nginx"
    echo ""
    echo "Cek status:"
    echo "  ${YELLOW}sudo $0 status${NC}"
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Instalasi selesai! Selamat menggunakan! 🚀${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
}

################################################################################
# V-Sentinel Closure Control Functions
################################################################################

create_vsentinel_env() {
    print_header "Creating V-Sentinel Environment Configuration"
    
    # Create /etc/ritapi directory
    print_step "Creating /etc/ritapi directory..."
    mkdir -p /etc/ritapi
    
    # Copy template and create vsentinel.env
    print_step "Creating vsentinel.env from template..."
    if [ -f "$SCRIPT_DIR/scripts/vsentinel.env.template" ]; then
        cp "$SCRIPT_DIR/scripts/vsentinel.env.template" /etc/ritapi/vsentinel.env
    else
        # Create default config
        cat > /etc/ritapi/vsentinel.env << 'EOF'
# V-Sentinel Environment Configuration - Gambling-Only Network Security
GAMBLING_ONLY=1
ALLOWED_DETECTION_TYPES=gambling
MODEL_NAME=v_sentinel_mlp
MODEL_VERSION=mlp_v2
POLICY_ID=V-SENTINEL-GOV-01
POLICY_VERSION=1.0

# Django / Database (PostgreSQL local by default)
DB_NAME=ritapi_vsentinel
DB_USER=ritapi
DB_PASSWORD=__AUTO_GENERATE__
DB_HOST=127.0.0.1
DB_PORT=5432

# Django security
SECRET_KEY=__AUTO_GENERATE__
EOF
    fi
    
    # Restrictive permissions: readable by root + web group (Gunicorn runs as www-data)

# Ensure required DB/Django keys exist even if the template is incomplete.
# Why: Django-environ reads os.environ; our installer and systemd load from /etc/ritapi/vsentinel.env.
if ! grep -q '^DB_NAME=' /etc/ritapi/vsentinel.env; then
    echo 'DB_NAME=ritapi_vsentinel' >> /etc/ritapi/vsentinel.env
fi
if ! grep -q '^DB_USER=' /etc/ritapi/vsentinel.env; then
    echo 'DB_USER=ritapi' >> /etc/ritapi/vsentinel.env
fi
if ! grep -q '^DB_PASSWORD=' /etc/ritapi/vsentinel.env; then
    echo 'DB_PASSWORD=__AUTO_GENERATE__' >> /etc/ritapi/vsentinel.env
fi
if ! grep -q '^DB_HOST=' /etc/ritapi/vsentinel.env; then
    echo 'DB_HOST=127.0.0.1' >> /etc/ritapi/vsentinel.env
fi
if ! grep -q '^DB_PORT=' /etc/ritapi/vsentinel.env; then
    echo 'DB_PORT=5432' >> /etc/ritapi/vsentinel.env
fi
if ! grep -q '^SECRET_KEY=' /etc/ritapi/vsentinel.env; then
    echo 'SECRET_KEY=__AUTO_GENERATE__' >> /etc/ritapi/vsentinel.env
fi
if ! grep -q '^ALLOWED_HOSTS=' /etc/ritapi/vsentinel.env; then
    echo 'ALLOWED_HOSTS=localhost,127.0.0.1' >> /etc/ritapi/vsentinel.env
fi

    chown root:"$DJANGO_GROUP" /etc/ritapi/vsentinel.env 2>/dev/null || chown root:www-data /etc/ritapi/vsentinel.env
    chmod 640 /etc/ritapi/vsentinel.env

    # Auto-generate secrets if placeholders are present.
    # Why: avoid shipping hardcoded credentials, and ensure Django has required env vars.
    local pw sk
    if grep -q "DB_PASSWORD=__AUTO_GENERATE__" /etc/ritapi/vsentinel.env; then
        if command -v openssl >/dev/null 2>&1; then
            pw="$(openssl rand -hex 24)"
        else
            pw="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
        fi
        sed -i "s/^DB_PASSWORD=__AUTO_GENERATE__/DB_PASSWORD=${pw}/" /etc/ritapi/vsentinel.env
    fi
    if grep -q "SECRET_KEY=__AUTO_GENERATE__" /etc/ritapi/vsentinel.env; then
        if command -v openssl >/dev/null 2>&1; then
            sk="$(openssl rand -hex 48)"
        else
            sk="$(python3 -c 'import secrets; print(secrets.token_hex(48))')"
        fi
        sed -i "s/^SECRET_KEY=__AUTO_GENERATE__/SECRET_KEY=${sk}/" /etc/ritapi/vsentinel.env
    fi

    print_success "V-Sentinel environment configuration created"
}

install_runtime_guard() {
    print_header "Installing Runtime Guard Script"
    
    # Create minifw_ai scripts directory if needed
    mkdir -p /opt/minifw_ai/scripts
    
    print_step "Installing vsentinel_runtime_guard.sh..."
    if [ -f "$SCRIPT_DIR/scripts/vsentinel_runtime_guard.sh" ]; then
        cp "$SCRIPT_DIR/scripts/vsentinel_runtime_guard.sh" /opt/minifw_ai/scripts/
    else
        print_warning "Runtime guard script not found in package"
    fi
    
    # Make executable
    chmod 755 /opt/minifw_ai/scripts/vsentinel_runtime_guard.sh
    
    print_success "Runtime guard script installed"
}

run_scope_gate() {
    print_header "Running Scope Gate Validation"
    
    if [ -f "$SCRIPT_DIR/scripts/vsentinel_scope_gate.sh" ]; then
        bash "$SCRIPT_DIR/scripts/vsentinel_scope_gate.sh"
        if [ $? -ne 0 ]; then
            print_error "Scope gate validation failed - installation cannot proceed"
            exit 1
        fi
    else
        print_warning "Scope gate script not found - skipping validation"
    fi
}

run_selftest() {
    print_header "Running Post-Installation Self-Test"
    
    if [ -f "$SCRIPT_DIR/scripts/vsentinel_selftest.sh" ]; then
        bash "$SCRIPT_DIR/scripts/vsentinel_selftest.sh"
        if [ $? -ne 0 ]; then
            print_warning "Some self-test checks failed - please review the output above"
        fi
    else
        print_warning "Self-test script not found - skipping verification"
    fi
}

install_logrotate() {
    print_header "Installing Log Rotation Configuration"
    
    print_step "Installing logrotate configuration..."
    if [ -f "$SCRIPT_DIR/scripts/logrotate.d/ritapi-vsentinel" ]; then
        mkdir -p /etc/logrotate.d
        cp "$SCRIPT_DIR/scripts/logrotate.d/ritapi-vsentinel" /etc/logrotate.d/
        chmod 644 /etc/logrotate.d/ritapi-vsentinel
        print_success "Logrotate configuration installed"
    else
        print_warning "Logrotate configuration not found in package"
    fi
}

################################################################################
# Uninstall Function
################################################################################

uninstall_all() {
    print_header "Uninstalling RITAPI & MiniFW-AI"
    
    echo -e "${YELLOW}PERINGATAN: Ini akan menghapus semua instalasi!${NC}"
    read -p "Lanjutkan dengan uninstall? (y/N): " confirm
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Uninstall dibatalkan"
        return
    fi
    
    print_step "Stopping services..."
    systemctl stop ritapi-gunicorn 2>/dev/null || true
    systemctl stop minifw-ai 2>/dev/null || true
    
    print_step "Disabling services..."
    systemctl disable ritapi-gunicorn 2>/dev/null || true
    systemctl disable minifw-ai 2>/dev/null || true
    
    print_step "Removing service files..."
    rm -f /etc/systemd/system/ritapi-gunicorn.service
    rm -f /etc/systemd/system/minifw-ai.service
    systemctl daemon-reload
    
    print_step "Removing application directories..."
    rm -rf "$DJANGO_PROJECT_DIR"
    rm -rf "$MINIFW_AI_DIR"
    
    print_step "Removing nginx configuration..."
    rm -f /etc/nginx/sites-enabled/ritapi
    rm -f /etc/nginx/sites-available/ritapi
    systemctl restart nginx 2>/dev/null || true
    
    print_step "Removing ipset..."
    ipset destroy minifw_block_v4 2>/dev/null || true
    
    print_success "Uninstallation complete"
    print_info "System packages (Python, Nginx, etc.) were NOT removed"
}

show_full_status() {
    show_banner
    print_header "RITAPI & MiniFW-AI Status"
    
    show_status
    
    echo ""
    echo -e "${CYAN}═══ Directories ═══${NC}"
    echo ""
    if [ -d "$DJANGO_PROJECT_DIR" ]; then
        echo -e "${GREEN}✓${NC} Django: $DJANGO_PROJECT_DIR"
    else
        echo -e "${RED}✗${NC} Django: Not installed"
    fi
    
    if [ -d "$MINIFW_AI_DIR" ]; then
        echo -e "${GREEN}✓${NC} MiniFW-AI: $MINIFW_AI_DIR"
    else
        echo -e "${RED}✗${NC} MiniFW-AI: Not installed"
    fi
    echo ""
    
    echo -e "${CYAN}═══ IPSet Status ═══${NC}"
    echo ""
    if ipset list minifw_block_v4 &>/dev/null; then
        BLOCKED_COUNT=$(ipset list minifw_block_v4 | grep -c "^[0-9]" || echo "0")
        echo -e "${GREEN}✓${NC} IPSet exists with $BLOCKED_COUNT blocked IPs"
    else
        echo -e "${RED}✗${NC} IPSet not found"
    fi
    echo ""
}

################################################################################
# Main Installation Flow
################################################################################

install_full() {
    show_banner
    
    echo -e "${CYAN}Installer ini akan menginstall:${NC}"
    echo "  1. RITAPI V-Sentinel (Django Web Application)"
    echo "  2. MiniFW-AI (Backend Security Service)"
    echo "  3. Nginx, Gunicorn, Redis, dan dependencies lainnya"
    echo ""
    echo -e "${YELLOW}Target instalasi:${NC}"
    echo "  - Django: $DJANGO_PROJECT_DIR"
    echo "  - MiniFW-AI: $MINIFW_AI_DIR"
    echo ""
    read -p "Lanjutkan dengan instalasi? (y/N): " confirm
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Instalasi dibatalkan"
        exit 0
    fi
    
    check_root
    verify_package_structure
    detect_web_user
    
    # V-Sentinel Closure Controls - Create environment early
    create_vsentinel_env
    ensure_allowed_hosts

    install_system_dependencies
    ensure_firewall_deps
    setup_postgres
    install_ritapi_django
    install_minifw_ai
    apply_minifw_crud_fix
    install_gunicorn_service
    configure_nginx
    
    # V-Sentinel Closure Controls - Validate before starting services
    run_scope_gate
    install_runtime_guard
    
    create_admin_user
    start_services
    
    # V-Sentinel Closure Controls - Verify after services started
    sleep 3
    run_selftest

    post_install_verify
    
    # Install log rotation at the end
    install_logrotate
    
    sleep 2
    show_status
    sleep 1
    show_completion_message
}

################################################################################
# Menu
################################################################################

show_menu() {
    show_banner
    
    echo -e "${CYAN}Pilih opsi:${NC}"
    echo ""
    echo "  ${GREEN}1.${NC} Install (Instalasi Lengkap)"
    echo "  ${BLUE}2.${NC} Status (Cek Services)"
    echo "  ${RED}3.${NC} Uninstall (Hapus Semua)"
    echo "  ${YELLOW}4.${NC} Exit"
    echo ""
    read -p "Pilihan [1-4]: " option
    
    case $option in
        1)
            install_full
            ;;
        2)
            show_full_status
            ;;
        3)
            uninstall_all
            ;;
        4)
            echo "Keluar..."
            exit 0
            ;;
        *)
            print_error "Pilihan tidak valid"
            sleep 2
            show_menu
            ;;
    esac
}

################################################################################
# Entry Point
################################################################################

if [ $# -eq 0 ]; then
    show_menu
else
    case "$1" in
        install)
            install_full
            ;;
        status)
            show_full_status
            ;;
        uninstall)
            uninstall_all
            ;;
        *)
            echo "Usage: $0 {install|status|uninstall}"
            exit 1
            ;;
    esac
fi
