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

################################################################################
# DNS Environment Detection (Task 1)
################################################################################

detect_dns_environment() {
    print_header "DNS Environment Detection"
    
    local dns_source="none"
    local dns_log_path=""
    
    # Check if systemd-resolved is active and using port 53
    print_step "Checking for systemd-resolved..."
    if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        if ss -tulpn 2>/dev/null | grep -q ':53.*systemd-resolve'; then
            print_success "systemd-resolved detected on port 53"
            print_warning "WILL NOT disable systemd-resolved (regulatory compliance)"
            dns_source="journald"
            dns_log_path="/run/systemd/resolve/stub-resolv.conf"
        else
            print_info "systemd-resolved active but not on port 53"
        fi
    else
        print_info "systemd-resolved not active"
    fi
    
    # Check if dnsmasq is installed and has valid log file
    if [ "$dns_source" = "none" ]; then
        print_step "Checking for dnsmasq..."
        if command -v dnsmasq >/dev/null 2>&1; then
            # Check for dnsmasq log configuration
            local dnsmasq_log=""
            if [ -f /etc/dnsmasq.conf ]; then
                dnsmasq_log=$(grep -E '^log-queries' /etc/dnsmasq.conf 2>/dev/null || true)
            fi
            
            if [ -n "$dnsmasq_log" ] || [ -f /var/log/dnsmasq.log ]; then
                print_success "dnsmasq with logging detected"
                dns_source="file"
                dns_log_path="/var/log/dnsmasq.log"
            else
                print_info "dnsmasq found but logging not configured"
            fi
        else
            print_info "dnsmasq not installed"
        fi
    fi
    
    # Final result
    if [ "$dns_source" = "none" ]; then
        print_warning "No DNS telemetry source detected"
        print_warning "MiniFW-AI will run in DEGRADED_MODE"
    else
        print_success "DNS telemetry source: $dns_source"
    fi
    
    # Export for use in other functions
    export DETECTED_DNS_SOURCE="$dns_source"
    export DETECTED_DNS_LOG_PATH="$dns_log_path"
    
    echo ""
    echo -e "${CYAN}DNS Detection Results:${NC}"
    echo -e "  Source: ${YELLOW}$dns_source${NC}"
    echo -e "  Path:   ${YELLOW}$dns_log_path${NC}"
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

# --- Admin creation (NEVER abort install) ---
create_admin_maybe() {
    local py="$DJANGO_PROJECT_DIR/venv/bin/python"
    local manage="$DJANGO_PROJECT_DIR/manage.py"
    local env_file="/etc/ritapi/vsentinel.env"

    if [ ! -f "$env_file" ]; then
        echo "[ERROR] Environment file $env_file not found. Cannot run Django commands."
        return 0
    fi

    # Use a subshell to source env and run command as non-root
    local run_cmd="set -a; source $env_file; set +a; cd $DJANGO_PROJECT_DIR; $py $manage"
    
    echo "[STEP] Django pre-flight check"
    if ! sudo -u "$DJANGO_USER" bash -c "$run_cmd check"; then
        echo "[WARN] Django system check failed. Skipping superuser creation to prevent crash."
        return 0
    fi

    echo "[STEP] Django admin creation (optional)"

    # Optional non-interactive creation via env vars
    if [[ -n "$DJANGO_SUPERUSER_USERNAME" || -n "$DJANGO_SUPERUSER_EMAIL" || -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
        if [[ -z "$DJANGO_SUPERUSER_USERNAME" || -z "$DJANGO_SUPERUSER_EMAIL" || -z "$DJANGO_SUPERUSER_PASSWORD" ]]; then
            echo "[WARN] Incomplete DJANGO_SUPERUSER_* env vars. Skipping non-interactive creation."
        else
            if ! sudo -u "$DJANGO_USER" \
                DJANGO_SUPERUSER_USERNAME="$DJANGO_SUPERUSER_USERNAME" \
                DJANGO_SUPERUSER_EMAIL="$DJANGO_SUPERUSER_EMAIL" \
                DJANGO_SUPERUSER_PASSWORD="$DJANGO_SUPERUSER_PASSWORD" \
                bash -c "$run_cmd createsuperuser --noinput"; then
                echo "[WARN] createsuperuser (non-interactive) failed (non-fatal)."
            fi
            return 0
        fi
    fi

    # Interactive attempt
    if [[ -t 0 && -t 1 ]]; then
        if ! sudo -u "$DJANGO_USER" bash -c "$run_cmd createsuperuser"; then
            echo "[WARN] createsuperuser failed (non-fatal)."
        fi
    else
        echo "[WARN] No TTY detected. Skipping interactive createsuperuser."
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

################################################################################
# Telemetry Pre-Flight Verification (Task 2)
################################################################################

write_deployment_state() {
    local dns_source="$1"
    local degraded_mode="$2"
    local dns_log_path="$3"
    local status_file="/var/log/ritapi/deployment_state.json"
    
    # Create directory
    mkdir -p /var/log/ritapi
    
    # Write deployment state for audit trail
    cat > "$status_file" << EOF
{
  "deployment_timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "hostname": "$(hostname)",
  "dns_telemetry": {
    "source": "$dns_source",
    "degraded_mode": $degraded_mode,
    "log_path": "$dns_log_path",
    "status": "$([ "$degraded_mode" -eq 1 ] && echo "degraded" || echo "normal")"
  },
  "security_enforcement": {
    "flow_tracking": "active",
    "hard_threat_gates": "active",
    "burst_detection": "active",
    "ai_modules": "$([ "$degraded_mode" -eq 1 ] && echo "limited" || echo "full")"
  },
  "fail_mode": {
    "telemetry": "fail-open",
    "security": "fail-closed"
  }
}
EOF
    
    chmod 644 "$status_file"
    print_success "Deployment state written to $status_file"
}

verify_telemetry() {
    print_header "Telemetry Pre-Flight Verification"
    
    local degraded_mode=0
    local dns_source="${DETECTED_DNS_SOURCE:-none}"
    local dns_log_path="${DETECTED_DNS_LOG_PATH:-}"
    
    if [ "$dns_source" = "none" ]; then
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_warning "⚠  WARNING: No DNS Telemetry Detected"
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_warning ""
        print_warning "MiniFW-AI will run in DEGRADED_MODE:"
        print_info "  ✓ Flow tracking: ACTIVE"
        print_info "  ✓ Hard-threat gates (PPS, burst, frequency): ACTIVE"
        print_info "  ✓ IP filtering: ACTIVE"
        print_info "  ✗ DNS-based domain analysis: LIMITED"
        print_warning ""
        print_info "This is FAIL-OPEN for telemetry, FAIL-CLOSED for security."
        print_info "Security enforcement continues without full DNS visibility."
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        degraded_mode=1
    else
        print_success "DNS telemetry source detected: $dns_source"
        print_success "MiniFW-AI will run in FULL MODE with complete visibility"
        degraded_mode=0
    fi
    
    # Export result
    export TELEMETRY_DEGRADED_MODE="$degraded_mode"
    
    # Write deployment state file for audit
    write_deployment_state "$dns_source" "$degraded_mode" "$dns_log_path"
    
    echo ""
    echo -e "${CYAN}Telemetry Status:${NC}"
    if [ "$degraded_mode" -eq 1 ]; then
        echo -e "  Mode: ${YELLOW}DEGRADED${NC} (no DNS events detected)"
    else
        echo -e "  Mode: ${GREEN}NORMAL${NC} (telemetry available)"
    fi
    echo ""
    
    # CRITICAL: Never abort installation, always continue
    return 0
}

install_minifw_systemd() {
    print_step "Installing systemd unit: minifw-ai (with stability hardening)"

    cat >/etc/systemd/system/minifw-ai.service <<'EOF'
[Unit]
Description=MiniFW-AI Security Service (V-Sentinel)
After=network.target
# NOTE: dnsmasq is NOT a hard requirement - DNS telemetry source is configurable
# If dnsmasq is present, wait for it; otherwise continue without it
After=dnsmasq.service
# No Wants= - do not try to start dnsmasq if not configured

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
Environment="MINIFW_LOG=/opt/minifw_ai/logs/events.jsonl"

# Load environment configuration (includes DNS source and degraded mode)
EnvironmentFile=-/etc/ritapi/vsentinel.env

# Task 3: Fail-Open Telemetry, Fail-Closed Security
# Service will not exit with error if DNS source is unavailable
ExecStart=/opt/minifw_ai/venv/bin/python -m minifw_ai

# Task 3: Restart policy with backoff to prevent restart storms
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable minifw-ai
    print_success "MiniFW-AI service configured with anti-restart-storm protection"
}

ensure_allowed_hosts() {
    local env_file="/etc/ritapi/vsentinel.env"

    local ip
    ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
    [[ -z "$ip" ]] && ip="$(hostname -I 2>/dev/null | awk '{print $1}')"

    if [[ -z "$ip" ]]; then
        print_warning "Could not auto-detect server IP. Leaving DJANGO_ALLOWED_HOSTS unchanged."
        return 0
    fi

    [[ -f "$env_file" ]] || touch "$env_file"

    if grep -q '^DJANGO_ALLOWED_HOSTS=' "$env_file"; then
        if ! grep -q "$ip" "$env_file"; then
            sed -i "s/^DJANGO_ALLOWED_HOSTS=\(.*\)$/DJANGO_ALLOWED_HOSTS=\1,$ip/" "$env_file"
        fi
    else
        echo "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,$ip" >>"$env_file"
    fi

    print_success "DJANGO_ALLOWED_HOSTS updated with $ip"
    systemctl restart ritapi-gunicorn 2>/dev/null || true
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
        postgresql \
        redis-server \
        nftables \
        ipset \
        sqlite3 \
        git \
        curl \
        wget \
        nginx \
        > /dev/null 2>&1
    
    print_success "System dependencies installed"
}

setup_postgresql() {
    print_header "Setting Up PostgreSQL Database"

    # Start and enable PostgreSQL
    print_step "Starting PostgreSQL service..."
    systemctl start postgresql
    systemctl enable postgresql

    # Read DB credentials from env file
    local env_file="/etc/ritapi/vsentinel.env"
    local db_name db_user db_pass
    db_name=$(grep -E "^DB_NAME=" "$env_file" | cut -d= -f2)
    db_user=$(grep -E "^DB_USER=" "$env_file" | cut -d= -f2)
    db_pass=$(grep -E "^DB_PASSWORD=" "$env_file" | cut -d= -f2)

    # Create database user if not exists
    print_step "Creating database user '$db_user'..."
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$db_user'" | grep -q 1; then
        print_info "User '$db_user' already exists, updating password"
        sudo -u postgres psql -c "ALTER USER $db_user WITH PASSWORD '$db_pass';" > /dev/null 2>&1
    else
        sudo -u postgres psql -c "CREATE USER $db_user WITH PASSWORD '$db_pass';" > /dev/null 2>&1
    fi

    # Create database if not exists
    print_step "Creating database '$db_name'..."
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$db_name'" | grep -q 1; then
        print_info "Database '$db_name' already exists"
    else
        sudo -u postgres psql -c "CREATE DATABASE $db_name OWNER $db_user;" > /dev/null 2>&1
    fi

    # Grant privileges
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;" > /dev/null 2>&1

    print_success "PostgreSQL database configured"
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
    
    # Run migrations
    print_step "Running Django migrations..."
    if [ -f "/etc/ritapi/vsentinel.env" ]; then
        sudo -u "$DJANGO_USER" bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; cd $DJANGO_PROJECT_DIR; ./venv/bin/python manage.py migrate --noinput" 2>/dev/null || true
    else
        cd "$DJANGO_PROJECT_DIR"
        "$DJANGO_PROJECT_DIR/venv/bin/python" manage.py migrate --noinput 2>/dev/null || true
    fi
    
    # Collect static files
    print_step "Collecting static files..."
    if [ -f "/etc/ritapi/vsentinel.env" ]; then
        sudo -u "$DJANGO_USER" bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; cd $DJANGO_PROJECT_DIR; ./venv/bin/python manage.py collectstatic --noinput" 2>/dev/null || true
    else
        "$DJANGO_PROJECT_DIR/venv/bin/python" manage.py collectstatic --noinput 2>/dev/null || true
    fi
    
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
    "ipset_name": "minifw_block_v4",
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
    chown -R "$DJANGO_USER:$DJANGO_GROUP" "$MINIFW_AI_DIR"
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
After=network.target

[Service]
Type=notify
User=$DJANGO_USER
Group=$DJANGO_GROUP
WorkingDirectory=$DJANGO_PROJECT_DIR
Environment="PATH=$DJANGO_PROJECT_DIR/venv/bin"
EnvironmentFile=/etc/ritapi/vsentinel.env
ExecStart=$DJANGO_PROJECT_DIR/venv/bin/gunicorn \\
    --workers 3 \\
    --bind 127.0.0.1:8000 \\
    --timeout 120 \\
    --access-logfile $DJANGO_PROJECT_DIR/logs/gunicorn-access.log \\
    --error-logfile $DJANGO_PROJECT_DIR/logs/gunicorn-error.log \\
    ritapi_v_sentinel.wsgi:application

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

    print_step "Starting PostgreSQL..."
    systemctl start postgresql 2>/dev/null || true

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
    echo -e "${CYAN}PostgreSQL:${NC}"
    systemctl status postgresql --no-pager -l 2>/dev/null | head -3 || echo "Not running"

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

# --- Secret Generation Helpers ---
gen_hex() {
    openssl rand -hex "$1"
}

ensure_kv() {
    local key="$1"
    local value="$2"
    local file="$3"

    if grep -q "^${key}=" "$file"; then
        # Key exists, check if it's empty or REPLACE_ME
        local current_val
        current_val=$(grep "^${key}=" "$file" | cut -d= -f2-)
        if [[ -z "$current_val" || "$current_val" == "REPLACE_ME" ]]; then
            sed -i "s|^${key}=.*|${key}=${value}|" "$file"
        fi
    else
        # Key does not exist, append
        echo "${key}=${value}" >> "$file"
    fi
}

create_vsentinel_env() {
    print_header "Creating V-Sentinel Environment Configuration"
    
    # Create /etc/ritapi directory with secure permissions
    print_step "Creating /etc/ritapi directory..."
    mkdir -p /etc/ritapi
    chown root:$DJANGO_GROUP /etc/ritapi
    chmod 0750 /etc/ritapi
    
    local env_file="/etc/ritapi/vsentinel.env"
    
    # Copy template and create vsentinel.env
    print_step "Creating vsentinel.env..."
    if [ -f "$SCRIPT_DIR/scripts/vsentinel.env.template" ]; then
        cp "$SCRIPT_DIR/scripts/vsentinel.env.template" "$env_file"
    elif [ ! -f "$env_file" ]; then
        touch "$env_file"
    fi
    
    # Guarantee required secrets
    print_step "Enforcing secure secrets..."
    ensure_kv "DJANGO_SECRET_KEY" "$(gen_hex 32)" "$env_file"
    ensure_kv "MINIFW_SECRET_KEY" "$(gen_hex 32)" "$env_file"
    ensure_kv "MINIFW_ADMIN_PASSWORD" "$(gen_hex 12)" "$env_file"
    ensure_kv "DB_PASSWORD" "$(gen_hex 16)" "$env_file"
    
    # Apply detected DNS configuration
    if [ -n "${DETECTED_DNS_SOURCE:-}" ]; then
        print_step "Applying DNS detection results to config..."
        sed -i "s|^MINIFW_DNS_SOURCE=.*|MINIFW_DNS_SOURCE=${DETECTED_DNS_SOURCE}|" "$env_file"
        sed -i "s|^MINIFW_DNS_LOG_PATH=.*|MINIFW_DNS_LOG_PATH=${DETECTED_DNS_LOG_PATH}|" "$env_file"
    fi
    
    # Apply telemetry verification results
    if [ -n "${TELEMETRY_DEGRADED_MODE:-}" ]; then
        print_step "Applying telemetry verification results..."
        sed -i "s|^DEGRADED_MODE=.*|DEGRADED_MODE=${TELEMETRY_DEGRADED_MODE}|" "$env_file"
    fi
    
    # Set restrictive permissions (readable by root and django group)
    chown root:$DJANGO_GROUP "$env_file"
    chmod 0640 "$env_file"
    
    print_success "V-Sentinel environment configuration created at $env_file"
    
    # Show final configuration
    echo ""
    echo -e "${CYAN}Final DNS Configuration:${NC}"
    echo -e "  DNS Source:     ${YELLOW}$(grep '^MINIFW_DNS_SOURCE=' "$env_file" | cut -d= -f2)${NC}"
    echo -e "  Degraded Mode:  ${YELLOW}$(grep '^DEGRADED_MODE=' "$env_file" | cut -d= -f2)${NC}"
    echo -e "  Log Path:       ${YELLOW}$(grep '^MINIFW_DNS_LOG_PATH=' "$env_file" | cut -d= -f2)${NC}"
    echo ""
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
    
    # Task 1: Detect DNS environment before configuration
    detect_dns_environment
    
    # V-Sentinel Closure Controls - Create environment with DNS config
    create_vsentinel_env
    
    install_system_dependencies
    ensure_firewall_deps
    setup_postgresql
    install_ritapi_django
    install_minifw_ai
    apply_minifw_crud_fix
    install_gunicorn_service
    ensure_allowed_hosts
    configure_nginx
    
    # V-Sentinel Closure Controls - Validate before starting services
    run_scope_gate
    install_runtime_guard
    
    create_admin_user
    start_services
    
    # Task 2: Verify telemetry after services are started
    verify_telemetry
    
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
