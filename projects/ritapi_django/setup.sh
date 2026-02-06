#!/bin/bash
# RitAPI V-Sentinel Setup & Installation Script
# This script sets up and installs RitAPI as a systemd service

set -e  # Exit on any error

APP_NAME="ritapi-v-sentinel"
PROJECT_ROOT=$(pwd)
INSTALL_DIR="/opt/ritapi-v-sentinel"
SERVICE_USER="ritapi"
SERVICE_NAME="ritapi-v-sentinel"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- HELPER FUNCTIONS ---
print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
command_exists() { command -v "$1" >/dev/null 2>&1; }

# --- GENERATE SECRET KEY ---
generate_secret_key() {
    # Generate a random secret key (alphanumeric only to avoid shell issues)
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1
}

# --- CHECK REQUIREMENTS ---
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root or with sudo"
    fi
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    
    # Check if version is 3.8 or higher
    if [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -ge 8 ]]; then
        print_success "Python $PYTHON_VERSION found"
    elif [[ "$PYTHON_MAJOR" -gt 3 ]]; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python $PYTHON_VERSION found, but Python 3.8 or higher is required"
    fi
    
    # Check PostgreSQL client
    if ! command_exists psql; then
        print_warning "PostgreSQL client not found. Installing..."
        apt-get update
        apt-get install -y postgresql-client
    fi
    print_success "PostgreSQL client found"
    
    # Check systemd
    if ! command_exists systemctl; then
        print_error "systemd is not available on this system"
    fi
    print_success "systemd found"
}

# --- ENV FILE CONFIGURATION ---
create_env_file() {
    print_status "Configuring environment variables..."
    
    # Default values
    local DEFAULT_DB_NAME="db_ritapi_advance"
    local DEFAULT_DB_USER="postgres"
    local DEFAULT_DB_HOST="localhost"
    local DEFAULT_DB_PORT="5432"
    local DEFAULT_BACKEND_URL="http://127.0.0.1:7003"
    
    echo ""
    echo "=========================================="
    echo "  RITAPI V-SENTINEL Configuration"
    echo "=========================================="
    echo ""
    
    # Django Settings
    echo "--- Django Settings ---"
    printf "Enter SECRET_KEY (leave empty to auto-generate): "
    read -r secret_key
    if [[ -z "$secret_key" ]]; then
        secret_key=$(generate_secret_key)
        print_status "Auto-generated SECRET_KEY"
    fi
    
    printf "Debug mode? [y/N]: "
    read -r debug_input
    if [[ "${debug_input,,}" == "y" ]]; then
        debug_mode="1"
    else
        debug_mode="0"
    fi
    
    printf "Enter ALLOWED_HOSTS (comma-separated, e.g., localhost,127.0.0.1,yourdomain.com) [localhost,127.0.0.1]: "
    read -r allowed_hosts
    allowed_hosts=${allowed_hosts:-"localhost,127.0.0.1"}
    
    printf "Enter ALLOW_IPS (comma-separated) [127.0.0.1]: "
    read -r allow_ips
    allow_ips=${allow_ips:-"127.0.0.1"}
    
    # Database Configuration
    echo ""
    echo "--- Database Configuration ---"
    printf "Enter PostgreSQL database name [$DEFAULT_DB_NAME]: "
    read -r db_name
    db_name=${db_name:-$DEFAULT_DB_NAME}
    
    printf "Enter PostgreSQL username [$DEFAULT_DB_USER]: "
    read -r db_user
    db_user=${db_user:-$DEFAULT_DB_USER}
    
    printf "Enter PostgreSQL password: "
    read -s db_password
    echo ""
    if [[ -z "$db_password" ]]; then
        print_error "Database password cannot be empty"
    fi
    
    printf "Enter PostgreSQL host [$DEFAULT_DB_HOST]: "
    read -r db_host
    db_host=${db_host:-$DEFAULT_DB_HOST}
    
    printf "Enter PostgreSQL port [$DEFAULT_DB_PORT]: "
    read -r db_port
    db_port=${db_port:-$DEFAULT_DB_PORT}
    
    # Service Configuration
    echo ""
    echo "--- Service Configuration ---"
    printf "Maximum services to monitor [2000]: "
    read -r max_services
    max_services=${max_services:-2000}
    
    printf "Maximum JSON body size in bytes [2097152 = 2MB]: "
    read -r max_json_body
    max_json_body=${max_json_body:-2097152}
    
    printf "Enforce JSON content type? [y/N]: "
    read -r enforce_json
    if [[ "${enforce_json,,}" == "y" ]]; then
        enforce_json_ct="True"
    else
        enforce_json_ct="False"
    fi
    
    # Security Settings
    echo ""
    echo "--- Security Settings (for Production) ---"
    printf "Enable HTTPS redirect? [y/N]: "
    read -r https_redirect
    if [[ "${https_redirect,,}" == "y" ]]; then
        ssl_redirect="True"
        session_cookie_secure="True"
        csrf_cookie_secure="True"
    else
        ssl_redirect="False"
        session_cookie_secure="False"
        csrf_cookie_secure="False"
    fi
    
    printf "Enter CSRF trusted origins (comma-separated URLs, e.g., https://yourdomain.com): "
    read -r csrf_origins
    
    # Notification Settings (Optional)
    echo ""
    echo "--- Notification Settings (Optional) ---"
    printf "Enable Telegram notifications? [y/N]: "
    read -r enable_telegram
    if [[ "${enable_telegram,,}" == "y" ]]; then
        printf "Enter Telegram Bot Token: "
        read -r telegram_token
        
        printf "Enter Telegram Chat ID: "
        read -r telegram_chat_id
    else
        telegram_token=""
        telegram_chat_id=""
    fi
    
    # Create .env file
    print_status "Creating .env file at $INSTALL_DIR/.env..."
    
    cat > "$INSTALL_DIR/.env" << EOF
# ========================================
# RITAPI V-SENTINEL Configuration
# Generated: $(date)
# ========================================

# --- Django Settings ---
SECRET_KEY=${secret_key}
DEBUG=${debug_mode}
ALLOWED_HOSTS=${allowed_hosts}
ALLOW_IPS=${allow_ips}
DJANGO_ENV=production
STATIC_ROOT=${INSTALL_DIR}/staticfiles
MEDIA_ROOT=${INSTALL_DIR}/media

# --- Database Configuration ---
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
DB_HOST=${db_host}
DB_PORT=${db_port}

# Legacy naming (for backward compatibility)
POSTGRES_DB=${db_name}
POSTGRES_USER=${db_user}
POSTGRES_PASSWORD=${db_password}
POSTGRES_HOST=${db_host}
POSTGRES_PORT=${db_port}
DATABASE_URL=postgresql://${db_user}:${db_password}@${db_host}:${db_port}/${db_name}

# --- Service Configuration ---
MAX_SERVICES=${max_services}
MAX_JSON_BODY=${max_json_body}
ENFORCE_JSON_CT=${enforce_json_ct}

# --- Security Settings ---
SECURE_SSL_REDIRECT=${ssl_redirect}
SESSION_COOKIE_SECURE=${session_cookie_secure}
CSRF_COOKIE_SECURE=${csrf_cookie_secure}
EOF

    # Add CSRF origins if provided
    if [[ -n "$csrf_origins" ]]; then
        echo "CSRF_TRUSTED_ORIGINS=${csrf_origins}" >> "$INSTALL_DIR/.env"
    else
        echo "# CSRF_TRUSTED_ORIGINS=https://yourdomain.com" >> "$INSTALL_DIR/.env"
    fi
    
    # Add Telegram settings if enabled
    if [[ -n "$telegram_token" ]]; then
        cat >> "$INSTALL_DIR/.env" << EOF

# --- Telegram Notification ---
TELEGRAM_BOT_TOKEN=${telegram_token}
TELEGRAM_CHAT_ID=${telegram_chat_id}
TELEGRAM_ENABLED=True
EOF
    else
        cat >> "$INSTALL_DIR/.env" << EOF

# --- Telegram Notification (Disabled) ---
# TELEGRAM_BOT_TOKEN=your-bot-token
# TELEGRAM_CHAT_ID=your-chat-id
# TELEGRAM_ENABLED=False
EOF
    fi
    
    # Set proper permissions
    chmod 600 "$INSTALL_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    
    print_success ".env file created successfully"
}

# --- SYSTEM USER CREATION ---
create_service_user() {
    print_status "Creating service user..."
    
    if id "$SERVICE_USER" &>/dev/null; then
        print_status "User $SERVICE_USER already exists"
    else
        useradd --system --home-dir "$INSTALL_DIR" --shell /bin/bash "$SERVICE_USER"
        print_success "User $SERVICE_USER created"
    fi
}

# --- INSTALLATION ---
install_application() {
    print_status "Installing application to $INSTALL_DIR..."
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy application files
    print_status "Copying application files..."
    rsync -av --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' \
        --exclude='.git' --exclude='*.log' --exclude='db.sqlite3' \
        --exclude='.env' \
        "$PROJECT_ROOT/" "$INSTALL_DIR/"
    
    # Create necessary directories
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/staticfiles"
    mkdir -p "$INSTALL_DIR/media"
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    
    print_success "Application installed"
}

# --- PYTHON ENVIRONMENT ---
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    cd "$INSTALL_DIR"
    
    # Create virtual environment as service user
    sudo -u "$SERVICE_USER" python3 -m venv venv
    
    # Upgrade pip
    print_status "Upgrading pip..."
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    
    # Install dependencies
    if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        print_status "Installing Python dependencies (this may take a few minutes)..."
        sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
        print_success "Dependencies installed"
    else
        print_error "requirements.txt not found"
    fi
}

# --- DATABASE SETUP ---
setup_database() {
    print_status "Setting up database..."
    
    # Load environment variables
    set -a
    source "$INSTALL_DIR/.env"
    set +a
    
    # Use DB_NAME or POSTGRES_DB
    DB_NAME="${DB_NAME:-$POSTGRES_DB}"
    DB_USER="${DB_USER:-$POSTGRES_USER}"
    DB_PASSWORD="${DB_PASSWORD:-$POSTGRES_PASSWORD}"
    DB_HOST="${DB_HOST:-$POSTGRES_HOST}"
    DB_PORT="${DB_PORT:-$POSTGRES_PORT}"
    
    # Ensure directories exist
    mkdir -p "$INSTALL_DIR/staticfiles"
    mkdir -p "$INSTALL_DIR/media"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/staticfiles" "$INSTALL_DIR/media"
    
    # Check if database exists
    export PGPASSWORD="$DB_PASSWORD"
    
    if psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt 2>/dev/null | cut -d \| -f1 | grep -qw "$DB_NAME"; then
        print_success "Database '$DB_NAME' already exists"
    else
        print_status "Creating database '$DB_NAME'..."
        createdb -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME"
        print_success "Database created"
    fi
    
    unset PGPASSWORD
    
    # Create a Python script that loads .env and runs Django commands
    cat > "$INSTALL_DIR/run_manage.py" << 'PYEOF'
#!/usr/bin/env python3
import os
import sys

# Read .env file and set environment variables
env_file = '/opt/ritapi-v-sentinel/.env'
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ritapi_v_sentinel.settings')

# Change to project directory
os.chdir('/opt/ritapi-v-sentinel')

# Run Django management command
if __name__ == '__main__':
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
PYEOF
    
    chmod +x "$INSTALL_DIR/run_manage.py"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/run_manage.py"
    
    # Run migrations
    cd "$INSTALL_DIR"
    print_status "Running database migrations..."
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/run_manage.py" migrate --noinput
    print_success "Database migrations completed"
    
    # Collect static files
    print_status "Collecting static files..."
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/run_manage.py" collectstatic --noinput
    print_success "Static files collected"
    
    # Keep the script for future use (don't remove it)
    print_status "Helper script created at: $INSTALL_DIR/run_manage.py"
}

# --- SUPERUSER CREATION ---
create_superuser() {
    print_status "Setting up admin user..."
    
    cd "$INSTALL_DIR"
    
    # Check if superuser exists using run_manage.py
    SUPERUSER_EXISTS=$(sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/run_manage.py" shell -c \
        "from django.contrib.auth import get_user_model; User = get_user_model(); print('yes' if User.objects.filter(is_superuser=True).exists() else 'no')" 2>/dev/null || echo "no")
    
    if [[ "$SUPERUSER_EXISTS" == "yes" ]]; then
        print_status "Superuser already exists"
    else
        echo ""
        printf "Create admin superuser? [Y/n]: "
        read -r create_admin
        
        if [[ "${create_admin,,}" != "n" ]]; then
            printf "Enter admin username [admin]: "
            read -r admin_user
            admin_user=${admin_user:-admin}
            
            printf "Enter admin email [admin@example.com]: "
            read -r admin_email
            admin_email=${admin_email:-admin@example.com}
            
            printf "Enter admin password: "
            read -s admin_password
            echo ""
            
            if [[ -z "$admin_password" ]]; then
                print_error "Admin password cannot be empty"
            fi
            
            sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/run_manage.py" shell << EOF
from django.contrib.auth import get_user_model;
User = get_user_model();
try:
    User.objects.create_superuser('${admin_user}', '${admin_email}', '${admin_password}')
    print('Superuser created successfully.')
except Exception as e:
    print(f'Error creating superuser: {e}')
EOF
            print_success "Superuser created"
        fi
    fi
}

# --- SYSTEMD SERVICE ---
create_systemd_service() {
    print_status "Creating systemd service..."
    
    # Install gunicorn if not present
    if ! sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" show gunicorn &>/dev/null; then
        print_status "Installing gunicorn..."
        sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install gunicorn
    fi
    
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=RITAPI V-Sentinel Service
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn \\
    --workers 4 \\
    --bind 0.0.0.0:8000 \\
    --timeout 120 \\
    --access-logfile ${INSTALL_DIR}/logs/access.log \\
    --error-logfile ${INSTALL_DIR}/logs/error.log \\
    --log-level info \\
    ritapi_v_sentinel.wsgi:application

Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}/logs ${INSTALL_DIR}/media ${INSTALL_DIR}/staticfiles

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    print_success "Systemd service created"
}

# --- SERVICE MANAGEMENT ---
start_service() {
    print_status "Starting ${SERVICE_NAME} service..."
    
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
    
    sleep 3
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_success "Service started successfully"
        echo ""
        print_status "Service status:"
        systemctl status "$SERVICE_NAME" --no-pager -l
    else
        print_error "Service failed to start. Check logs with: journalctl -u ${SERVICE_NAME} -n 50"
    fi
}

stop_service() {
    print_status "Stopping ${SERVICE_NAME} service..."
    systemctl stop "$SERVICE_NAME"
    systemctl disable "$SERVICE_NAME"
    print_success "Service stopped"
}

restart_service() {
    print_status "Restarting ${SERVICE_NAME} service..."
    systemctl restart "$SERVICE_NAME"
    sleep 2
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_success "Service restarted successfully"
    else
        print_error "Service failed to restart. Check logs with: journalctl -u ${SERVICE_NAME} -n 50"
    fi
}

# --- NGINX CONFIGURATION (OPTIONAL) ---
setup_nginx() {
    if ! command_exists nginx; then
        print_warning "Nginx not found. Skipping nginx configuration."
        return
    fi
    
    echo ""
    printf "Configure Nginx reverse proxy? [y/N]: "
    read -r setup_nginx_input
    
    if [[ "${setup_nginx_input,,}" != "y" ]]; then
        return
    fi
    
    printf "Enter domain name (e.g., ritapi.yourdomain.com): "
    read -r domain_name
    
    if [[ -z "$domain_name" ]]; then
        print_warning "Domain name empty. Skipping nginx configuration."
        return
    fi
    
    print_status "Creating nginx configuration..."
    
    cat > "/etc/nginx/sites-available/${SERVICE_NAME}" << EOF
upstream ritapi_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name ${domain_name};

    client_max_body_size 10M;

    access_log ${INSTALL_DIR}/logs/nginx_access.log;
    error_log ${INSTALL_DIR}/logs/nginx_error.log;

    location /static/ {
        alias ${INSTALL_DIR}/staticfiles/;
    }

    location /media/ {
        alias ${INSTALL_DIR}/media/;
    }

    location / {
        proxy_pass http://ritapi_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
}
EOF

    # Enable site
    ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/"
    
    # Test nginx configuration
    if nginx -t; then
        systemctl reload nginx
        print_success "Nginx configured for $domain_name"
        print_status "Access your application at: http://$domain_name"
    else
        print_error "Nginx configuration test failed"
    fi
}

# --- UNINSTALL ---
uninstall() {
    print_warning "This will completely remove RITAPI V-Sentinel from your system"
    printf "Are you sure? [y/N]: "
    read -r confirm
    
    if [[ "${confirm,,}" != "y" ]]; then
        print_status "Uninstall cancelled"
        exit 0
    fi
    
    # Stop and disable service
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        print_status "Stopping service..."
        systemctl stop "$SERVICE_NAME"
    fi
    
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    
    # Remove systemd service
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    
    # Remove nginx configuration
    if [[ -f "/etc/nginx/sites-enabled/${SERVICE_NAME}" ]]; then
        rm -f "/etc/nginx/sites-enabled/${SERVICE_NAME}"
        rm -f "/etc/nginx/sites-available/${SERVICE_NAME}"
        systemctl reload nginx 2>/dev/null || true
    fi
    
    # Remove installation directory
    printf "Remove installation directory ($INSTALL_DIR)? [y/N]: "
    read -r remove_dir
    
    if [[ "${remove_dir,,}" == "y" ]]; then
        rm -rf "$INSTALL_DIR"
        print_success "Installation directory removed"
    fi
    
    # Remove service user
    printf "Remove service user ($SERVICE_USER)? [y/N]: "
    read -r remove_user
    
    if [[ "${remove_user,,}" == "y" ]]; then
        userdel "$SERVICE_USER" 2>/dev/null || true
        print_success "Service user removed"
    fi
    
    print_success "Uninstall completed"
}

# --- USAGE ---
show_usage() {
    cat << EOF
RITAPI V-Sentinel Installation Script

Usage: $0 [COMMAND]

Commands:
  install       - Full installation (user, app, database, service)
  start         - Start the service
  stop          - Stop the service
  restart       - Restart the service
  status        - Show service status
  logs          - Show service logs
  uninstall     - Completely remove RITAPI V-Sentinel
  help          - Show this help message

Examples:
  sudo $0 install     # Install RITAPI V-Sentinel
  sudo $0 start       # Start the service
  sudo $0 status      # Check service status
  sudo $0 logs        # View logs
  sudo $0 uninstall   # Uninstall completely

After installation:
  - Service runs on: http://0.0.0.0:8000
  - Logs location: $INSTALL_DIR/logs/
  - Configuration: $INSTALL_DIR/.env
  - Access dashboard: http://your-server-ip:8000/login/

EOF
}

fix_settings_py() {
    print_status "Configuring Django settings for production..."
    
    local SETTINGS_FILE="$INSTALL_DIR/ritapi_v_sentinel/settings.py"
    
    # Backup original settings
    if [[ ! -f "$SETTINGS_FILE.backup" ]]; then
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup"
        print_status "Backup created: settings.py.backup"
    fi
    
    # Check if our configuration already exists
    if grep -q "# Production Static Files Configuration" "$SETTINGS_FILE"; then
        print_status "Static files configuration already exists"
        return
    fi
    
    print_status "Adding static and media files configuration..."
    
    # Replace the simple STATIC_URL line with full configuration
    # Find the line "STATIC_URL = 'static/'" and replace entire section
    sed -i "/^STATIC_URL = 'static\/'/d" "$SETTINGS_FILE"
    sed -i "/^# Static files (CSS, JavaScript, Images)/d" "$SETTINGS_FILE"
    sed -i "/^# https:\/\/docs.djangoproject.com\/en\/.*\/howto\/static-files\//d" "$SETTINGS_FILE"
    
    # Add complete static files configuration at the end before LOGIN_URL
    # Find the line with LOGIN_URL and insert before it
    sed -i "/^LOGIN_URL = 'login'/i\\
# ============================================\\
# Production Static Files Configuration\\
# ============================================\\
STATIC_URL = '/static/'\\
STATIC_ROOT = env('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))\\
\\
MEDIA_URL = '/media/'\\
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))\\
\\
STATICFILES_DIRS = []\\
\\
# WhiteNoise configuration for serving static files in production\\
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'\\
\\
" "$SETTINGS_FILE"
    
    # Also update SECRET_KEY and DEBUG to use env
    sed -i "s/^SECRET_KEY = 'django-insecure-.*/SECRET_KEY = env('SECRET_KEY', default='django-insecure-s30+*@8(x@j#38wrkv_d1svrkr1k@tarrm4gz*fbf0imv*\&ef_')/" "$SETTINGS_FILE"
    sed -i "s/^DEBUG = True/DEBUG = env.bool('DEBUG', default=False)/" "$SETTINGS_FILE"
    sed -i "s/^ALLOWED_HOSTS = \[\]/ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])/" "$SETTINGS_FILE"
    
    # Add WhiteNoise to MIDDLEWARE if not already there
    if ! grep -q "whitenoise.middleware.WhiteNoiseMiddleware" "$SETTINGS_FILE"; then
        sed -i "/django.middleware.security.SecurityMiddleware/a\    'whitenoise.middleware.WhiteNoiseMiddleware'," "$SETTINGS_FILE"
        print_status "WhiteNoise middleware added"
    fi
    
    chown "$SERVICE_USER:$SERVICE_USER" "$SETTINGS_FILE"
    
    print_success "Django settings configured for production"
}

# --- MAIN ---
main() {
    case "${1:-install}" in
        "install")
            echo ""
            echo "=========================================="
            echo "  RITAPI V-SENTINEL Installation"
            echo "=========================================="
            echo ""
            
            check_requirements
            create_service_user
            install_application
            fix_settings_py
            setup_python_env
            create_env_file
            setup_database
            create_superuser
            create_systemd_service
            start_service
            setup_nginx
            
            echo ""
            echo "=========================================="
            print_success "Installation completed!"
            echo "=========================================="
            echo ""
            echo "Service Information:"
            echo "  - Status: systemctl status $SERVICE_NAME"
            echo "  - Logs: journalctl -u $SERVICE_NAME -f"
            echo "  - Start: systemctl start $SERVICE_NAME"
            echo "  - Stop: systemctl stop $SERVICE_NAME"
            echo "  - Restart: systemctl restart $SERVICE_NAME"
            echo ""
            echo "Access Points:"
            echo "  - Dashboard: http://your-server-ip:8000/login/"
            echo "  - Admin: http://your-server-ip:8000/admin/"
            echo ""
            echo "Configuration:"
            echo "  - Environment: $INSTALL_DIR/.env"
            echo "  - Logs: $INSTALL_DIR/logs/"
            echo ""
            ;;
        "start")
            start_service
            ;;
        "stop")
            stop_service
            ;;
        "restart")
            restart_service
            ;;
        "status")
            systemctl status "$SERVICE_NAME"
            ;;
        "logs")
            journalctl -u "$SERVICE_NAME" -f
            ;;
        "uninstall")
            uninstall
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Check if script is run from the correct directory
if [[ ! -f "manage.py" ]]; then
    print_error "This script must be run from the project root directory (where manage.py is located)"
fi

# Run main function
main "$@"