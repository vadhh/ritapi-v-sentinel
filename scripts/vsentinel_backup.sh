#!/bin/bash

################################################################################
# V-Sentinel Pre-Upgrade Backup Script
#
# Creates a timestamped backup of database, config, code, and migration state.
# Designed to run before upgrades via install.sh or manually by operators.
#
# Usage:
#   sudo bash vsentinel_backup.sh              # Full backup
#   sudo bash vsentinel_backup.sh --db-only    # Database only
#   sudo bash vsentinel_backup.sh --dry-run    # Show what would be backed up
#
# Output: /var/backups/ritapi/backup_YYYYMMDD_HHMMSS/
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Paths
BACKUP_BASE="/var/backups/ritapi"
DJANGO_PROJECT_DIR="/opt/ritapi_v_sentinel"
MINIFW_AI_DIR="/opt/minifw_ai"
ENV_FILE="/etc/ritapi/vsentinel.env"
BACKUP_RETAIN_COUNT="${BACKUP_RETAIN_COUNT:-5}"

# Timestamp for this backup
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_BASE}/backup_${TIMESTAMP}"

# Flags
DRY_RUN=false
DB_ONLY=false

################################################################################
# Helper Functions
################################################################################

print_success() { echo -e "${GREEN}[BACKUP] $1${NC}"; }
print_error()   { echo -e "${RED}[BACKUP ERROR] $1${NC}"; }
print_warning() { echo -e "${YELLOW}[BACKUP WARN] $1${NC}"; }
print_info()    { echo -e "${CYAN}[BACKUP] $1${NC}"; }

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dry-run     Show what would be backed up without doing it"
    echo "  --db-only     Backup database only (skip code and config)"
    echo "  --help        Show this help message"
    echo ""
    echo "Environment:"
    echo "  BACKUP_RETAIN_COUNT  Number of backups to keep (default: 5)"
    exit 0
}

################################################################################
# Parse Arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=true; shift ;;
        --db-only)  DB_ONLY=true; shift ;;
        --help)     usage ;;
        *)          print_error "Unknown option: $1"; usage ;;
    esac
done

################################################################################
# Pre-flight Checks
################################################################################

preflight_check() {
    local errors=0

    # Must be root
    if [ "$EUID" -ne 0 ]; then
        print_error "Must be run as root (use sudo)"
        exit 1
    fi

    # Env file must exist (contains DB credentials)
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Environment file not found: $ENV_FILE"
        print_error "Cannot determine database credentials for backup"
        exit 1
    fi

    # At least one of the project dirs should exist
    if [ ! -d "$DJANGO_PROJECT_DIR" ] && [ ! -d "$MINIFW_AI_DIR" ]; then
        print_error "No installation found at $DJANGO_PROJECT_DIR or $MINIFW_AI_DIR"
        print_error "Nothing to back up"
        exit 1
    fi

    # Check for pg_dump (needed for DB backup)
    if ! command -v pg_dump >/dev/null 2>&1; then
        print_warning "pg_dump not found - database backup will be skipped"
        errors=1
    fi

    return 0
}

################################################################################
# Read Database Credentials
################################################################################

load_db_credentials() {
    # Source env file to get DB credentials
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a

    # Check for external DB mode first
    local pg_mode="${PG_MODE:-auto}"

    if [ "$pg_mode" = "external" ] && [ -n "$DATABASE_URL" ]; then
        DB_CONNECTION_MODE="external"
        print_info "Using DATABASE_URL for external database"
    else
        DB_CONNECTION_MODE="local"
        # Verify we have local credentials
        if [ -z "${DB_NAME:-}" ] || [ -z "${DB_USER:-}" ]; then
            print_error "DB_NAME or DB_USER not set in $ENV_FILE"
            exit 1
        fi
    fi
}

################################################################################
# Backup Functions
################################################################################

backup_database() {
    print_info "Backing up database..."

    if ! command -v pg_dump >/dev/null 2>&1; then
        print_warning "pg_dump not available, skipping database backup"
        return 0
    fi

    local dump_file="${BACKUP_DIR}/db_dump.sql"

    if [ "$DRY_RUN" = true ]; then
        if [ "$DB_CONNECTION_MODE" = "external" ]; then
            print_info "[DRY RUN] Would run: pg_dump using DATABASE_URL > $dump_file"
        else
            print_info "[DRY RUN] Would run: pg_dump -h ${DB_HOST:-127.0.0.1} -p ${DB_PORT:-5432} -U ${DB_USER} ${DB_NAME} > $dump_file"
        fi
        return 0
    fi

    if [ "$DB_CONNECTION_MODE" = "external" ]; then
        if pg_dump "$DATABASE_URL" > "$dump_file" 2>/dev/null; then
            local size
            size=$(du -sh "$dump_file" | cut -f1)
            print_success "Database backed up ($size): $dump_file"
        else
            print_error "Database backup failed (external mode)"
            return 1
        fi
    else
        local pg_host="${DB_HOST:-127.0.0.1}"
        local pg_port="${DB_PORT:-5432}"

        if PGPASSWORD="${DB_PASSWORD}" pg_dump \
            -h "$pg_host" \
            -p "$pg_port" \
            -U "$DB_USER" \
            "$DB_NAME" > "$dump_file" 2>/dev/null; then
            local size
            size=$(du -sh "$dump_file" | cut -f1)
            print_success "Database backed up ($size): $dump_file"
        else
            # Fallback: try as postgres user (local peer auth)
            if sudo -u postgres pg_dump "$DB_NAME" > "$dump_file" 2>/dev/null; then
                local size
                size=$(du -sh "$dump_file" | cut -f1)
                print_success "Database backed up via peer auth ($size): $dump_file"
            else
                print_error "Database backup failed"
                return 1
            fi
        fi
    fi
}

backup_config() {
    print_info "Backing up configuration..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would copy: $ENV_FILE -> ${BACKUP_DIR}/vsentinel.env"
        return 0
    fi

    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${BACKUP_DIR}/vsentinel.env"
        chmod 600 "${BACKUP_DIR}/vsentinel.env"
        print_success "Config backed up: ${BACKUP_DIR}/vsentinel.env"
    else
        print_warning "Config file not found: $ENV_FILE"
    fi
}

backup_code() {
    print_info "Backing up application code..."

    # Backup Django code (excluding venv, __pycache__, .pyc)
    if [ -d "$DJANGO_PROJECT_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            print_info "[DRY RUN] Would create: ${BACKUP_DIR}/ritapi_code.tar.gz from $DJANGO_PROJECT_DIR"
        else
            tar czf "${BACKUP_DIR}/ritapi_code.tar.gz" \
                --exclude='venv' \
                --exclude='__pycache__' \
                --exclude='*.pyc' \
                --exclude='logs/*.log' \
                -C "$(dirname "$DJANGO_PROJECT_DIR")" \
                "$(basename "$DJANGO_PROJECT_DIR")" 2>/dev/null
            local size
            size=$(du -sh "${BACKUP_DIR}/ritapi_code.tar.gz" | cut -f1)
            print_success "Django code backed up ($size): ritapi_code.tar.gz"
        fi
    else
        print_warning "Django directory not found: $DJANGO_PROJECT_DIR"
    fi

    # Backup MiniFW code (excluding venv, __pycache__, .pyc, large logs)
    if [ -d "$MINIFW_AI_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            print_info "[DRY RUN] Would create: ${BACKUP_DIR}/minifw_code.tar.gz from $MINIFW_AI_DIR"
        else
            tar czf "${BACKUP_DIR}/minifw_code.tar.gz" \
                --exclude='venv' \
                --exclude='__pycache__' \
                --exclude='*.pyc' \
                --exclude='logs/*.jsonl' \
                --exclude='logs/*.log' \
                -C "$(dirname "$MINIFW_AI_DIR")" \
                "$(basename "$MINIFW_AI_DIR")" 2>/dev/null
            local size
            size=$(du -sh "${BACKUP_DIR}/minifw_code.tar.gz" | cut -f1)
            print_success "MiniFW code backed up ($size): minifw_code.tar.gz"
        fi
    else
        print_warning "MiniFW directory not found: $MINIFW_AI_DIR"
    fi
}

backup_migration_state() {
    print_info "Recording migration state..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would run: manage.py showmigrations > ${BACKUP_DIR}/migration_state.txt"
        return 0
    fi

    local migration_file="${BACKUP_DIR}/migration_state.txt"
    local py="${DJANGO_PROJECT_DIR}/venv/bin/python"
    local manage="${DJANGO_PROJECT_DIR}/manage.py"

    if [ -f "$py" ] && [ -f "$manage" ]; then
        if [ -f "$ENV_FILE" ]; then
            sudo -u www-data bash -c "set -a; source $ENV_FILE; set +a; cd $DJANGO_PROJECT_DIR; $py $manage showmigrations" > "$migration_file" 2>/dev/null || true
        else
            cd "$DJANGO_PROJECT_DIR"
            "$py" "$manage" showmigrations > "$migration_file" 2>/dev/null || true
        fi

        if [ -s "$migration_file" ]; then
            print_success "Migration state recorded: $migration_file"
        else
            print_warning "Could not capture migration state (file empty)"
        fi
    else
        print_warning "Django manage.py not found, skipping migration state"
    fi
}

create_manifest() {
    print_info "Creating backup manifest..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would create: ${BACKUP_DIR}/manifest.json"
        return 0
    fi

    # Gather version info
    local pg_version="unknown"
    if command -v psql >/dev/null 2>&1; then
        pg_version=$(psql --version 2>/dev/null | head -1 || echo "unknown")
    fi

    local django_version="unknown"
    local py="${DJANGO_PROJECT_DIR}/venv/bin/python"
    if [ -f "$py" ]; then
        django_version=$("$py" -c "import django; print(django.get_version())" 2>/dev/null || echo "unknown")
    fi

    # List backup files
    local files_json="["
    local first=true
    for f in "${BACKUP_DIR}"/*; do
        [ -f "$f" ] || continue
        local fname
        fname=$(basename "$f")
        [ "$fname" = "manifest.json" ] && continue
        local fsize
        fsize=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$first" = true ]; then
            first=false
        else
            files_json+=","
        fi
        files_json+="{\"name\":\"$fname\",\"size\":$fsize}"
    done
    files_json+="]"

    cat > "${BACKUP_DIR}/manifest.json" << EOF
{
  "version": "1.0",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "timestamp_local": "$(date +"%Y-%m-%d %H:%M:%S %Z")",
  "hostname": "$(hostname)",
  "backup_dir": "${BACKUP_DIR}",
  "pg_version": "$pg_version",
  "django_version": "$django_version",
  "db_connection_mode": "$DB_CONNECTION_MODE",
  "db_name": "${DB_NAME:-N/A}",
  "files": $files_json
}
EOF

    print_success "Manifest created: ${BACKUP_DIR}/manifest.json"
}

################################################################################
# Retention: Remove Old Backups
################################################################################

cleanup_old_backups() {
    print_info "Checking backup retention (keep last $BACKUP_RETAIN_COUNT)..."

    if [ "$DRY_RUN" = true ]; then
        local count
        count=$(find "$BACKUP_BASE" -maxdepth 1 -type d -name 'backup_*' 2>/dev/null | wc -l)
        print_info "[DRY RUN] Found $count existing backups (retain: $BACKUP_RETAIN_COUNT)"
        return 0
    fi

    # List backup dirs sorted oldest first, skip the most recent N
    local backups
    backups=$(find "$BACKUP_BASE" -maxdepth 1 -type d -name 'backup_*' 2>/dev/null | sort)
    local count
    count=$(echo "$backups" | grep -c . || true)

    if [ "$count" -gt "$BACKUP_RETAIN_COUNT" ]; then
        local to_remove
        to_remove=$((count - BACKUP_RETAIN_COUNT))
        echo "$backups" | head -n "$to_remove" | while read -r old_dir; do
            print_info "Removing old backup: $old_dir"
            rm -rf "$old_dir"
        done
        print_success "Cleaned up $to_remove old backup(s)"
    else
        print_info "Retention OK ($count backups, limit $BACKUP_RETAIN_COUNT)"
    fi
}

################################################################################
# Main
################################################################################

main() {
    echo ""
    print_info "========================================"
    print_info "  V-Sentinel Backup - $TIMESTAMP"
    print_info "========================================"
    echo ""

    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY RUN MODE - no changes will be made"
        echo ""
    fi

    preflight_check
    load_db_credentials

    # Create backup directory
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$BACKUP_DIR"
        chmod 700 "$BACKUP_DIR"
    fi

    # Run backups
    backup_database

    if [ "$DB_ONLY" = false ]; then
        backup_config
        backup_code
        backup_migration_state
    fi

    create_manifest

    # Secure the backup directory
    if [ "$DRY_RUN" = false ]; then
        chmod -R 600 "${BACKUP_DIR}"/*
        chmod 700 "$BACKUP_DIR"
    fi

    cleanup_old_backups

    echo ""
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN complete. No backup was created."
    else
        print_success "========================================"
        print_success "  Backup complete: $BACKUP_DIR"
        print_success "========================================"
    fi
    echo ""
}

main
