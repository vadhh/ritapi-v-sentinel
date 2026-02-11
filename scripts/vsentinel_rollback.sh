#!/bin/bash

################################################################################
# V-Sentinel Rollback Script
#
# Restores a previous backup created by vsentinel_backup.sh.
# Covers: database, config, application code, and services.
#
# Usage:
#   sudo bash vsentinel_rollback.sh                          # Dry-run with latest backup
#   sudo bash vsentinel_rollback.sh --confirm                # Execute with latest backup
#   sudo bash vsentinel_rollback.sh /path/to/backup --confirm  # Execute with specific backup
#   sudo bash vsentinel_rollback.sh --list                   # List available backups
#
# Safety: Requires --confirm flag to execute. Dry-run by default.
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

# Flags
CONFIRM=false
DRY_RUN=true
LIST_ONLY=false
BACKUP_DIR=""
SKIP_DB=false
SKIP_CODE=false
SKIP_CONFIG=false

################################################################################
# Helper Functions
################################################################################

print_success() { echo -e "${GREEN}[ROLLBACK] $1${NC}"; }
print_error()   { echo -e "${RED}[ROLLBACK ERROR] $1${NC}"; }
print_warning() { echo -e "${YELLOW}[ROLLBACK WARN] $1${NC}"; }
print_info()    { echo -e "${CYAN}[ROLLBACK] $1${NC}"; }

usage() {
    echo "Usage: $0 [BACKUP_DIR] [OPTIONS]"
    echo ""
    echo "Arguments:"
    echo "  BACKUP_DIR        Path to backup directory (default: latest backup)"
    echo ""
    echo "Options:"
    echo "  --confirm         Actually execute the rollback (default: dry-run)"
    echo "  --list            List available backups and exit"
    echo "  --skip-db         Skip database restore"
    echo "  --skip-code       Skip code restore"
    echo "  --skip-config     Skip config restore"
    echo "  --help            Show this help message"
    echo ""
    echo "Without --confirm, the script runs in dry-run mode showing what would happen."
    exit 0
}

################################################################################
# Parse Arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case "$1" in
        --confirm)     CONFIRM=true; DRY_RUN=false; shift ;;
        --list)        LIST_ONLY=true; shift ;;
        --skip-db)     SKIP_DB=true; shift ;;
        --skip-code)   SKIP_CODE=true; shift ;;
        --skip-config) SKIP_CONFIG=true; shift ;;
        --help)        usage ;;
        -*)            print_error "Unknown option: $1"; usage ;;
        *)
            if [ -z "$BACKUP_DIR" ]; then
                BACKUP_DIR="$1"
            else
                print_error "Unexpected argument: $1"
                usage
            fi
            shift
            ;;
    esac
done

################################################################################
# List Backups
################################################################################

list_backups() {
    echo ""
    print_info "Available backups in $BACKUP_BASE:"
    echo ""

    if [ ! -d "$BACKUP_BASE" ]; then
        print_warning "No backup directory found at $BACKUP_BASE"
        return 0
    fi

    local found=false
    for dir in "$BACKUP_BASE"/backup_*; do
        [ -d "$dir" ] || continue
        found=true

        local manifest="$dir/manifest.json"
        local dirname
        dirname=$(basename "$dir")

        if [ -f "$manifest" ]; then
            local ts
            ts=$(grep '"timestamp_local"' "$manifest" | cut -d'"' -f4 2>/dev/null || echo "unknown")
            local host
            host=$(grep '"hostname"' "$manifest" | cut -d'"' -f4 2>/dev/null || echo "unknown")

            # Count files
            local file_count
            file_count=$(find "$dir" -maxdepth 1 -type f | wc -l)
            local total_size
            total_size=$(du -sh "$dir" | cut -f1)

            echo -e "  ${GREEN}$dirname${NC}  |  $ts  |  $host  |  ${total_size}  |  ${file_count} files"
        else
            echo -e "  ${YELLOW}$dirname${NC}  |  (no manifest)"
        fi
    done

    if [ "$found" = false ]; then
        print_warning "No backups found"
    fi
    echo ""
}

################################################################################
# Find Latest Backup
################################################################################

find_latest_backup() {
    local latest
    latest=$(find "$BACKUP_BASE" -maxdepth 1 -type d -name 'backup_*' 2>/dev/null | sort | tail -1)

    if [ -z "$latest" ] || [ ! -d "$latest" ]; then
        print_error "No backups found in $BACKUP_BASE"
        exit 1
    fi

    echo "$latest"
}

################################################################################
# Validate Backup
################################################################################

validate_backup() {
    local dir="$1"

    print_info "Validating backup: $dir"

    if [ ! -d "$dir" ]; then
        print_error "Backup directory does not exist: $dir"
        exit 1
    fi

    # Check manifest
    if [ ! -f "$dir/manifest.json" ]; then
        print_error "No manifest.json found in backup - invalid backup"
        exit 1
    fi

    # Report what's available
    local has_db=false has_config=false has_django=false has_minifw=false has_migrations=false

    [ -f "$dir/db_dump.sql" ] && has_db=true
    [ -f "$dir/vsentinel.env" ] && has_config=true
    [ -f "$dir/ritapi_code.tar.gz" ] && has_django=true
    [ -f "$dir/minifw_code.tar.gz" ] && has_minifw=true
    [ -f "$dir/migration_state.txt" ] && has_migrations=true

    echo ""
    echo "  Backup contents:"
    echo -e "    Database dump:    $([ "$has_db" = true ] && echo "${GREEN}YES${NC}" || echo "${YELLOW}NO${NC}")"
    echo -e "    Config:           $([ "$has_config" = true ] && echo "${GREEN}YES${NC}" || echo "${YELLOW}NO${NC}")"
    echo -e "    Django code:      $([ "$has_django" = true ] && echo "${GREEN}YES${NC}" || echo "${YELLOW}NO${NC}")"
    echo -e "    MiniFW code:      $([ "$has_minifw" = true ] && echo "${GREEN}YES${NC}" || echo "${YELLOW}NO${NC}")"
    echo -e "    Migration state:  $([ "$has_migrations" = true ] && echo "${GREEN}YES${NC}" || echo "${YELLOW}NO${NC}")"
    echo ""

    # Show manifest info
    local ts
    ts=$(grep '"timestamp_local"' "$dir/manifest.json" | cut -d'"' -f4 2>/dev/null || echo "unknown")
    print_info "Backup timestamp: $ts"
}

################################################################################
# Rollback Functions
################################################################################

stop_services() {
    print_info "Stopping application services..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would stop: ritapi-gunicorn, minifw-ai"
        return 0
    fi

    # Stop app services (Nginx stays up for potential maintenance page)
    systemctl stop ritapi-gunicorn 2>/dev/null || true
    systemctl stop minifw-ai 2>/dev/null || true

    # Wait for services to fully stop
    sleep 2
    print_success "Services stopped (Nginx left running)"
}

rollback_database() {
    local dir="$1"

    if [ "$SKIP_DB" = true ]; then
        print_info "Skipping database restore (--skip-db)"
        return 0
    fi

    if [ ! -f "$dir/db_dump.sql" ]; then
        print_warning "No database dump found, skipping database restore"
        return 0
    fi

    print_info "Restoring database..."

    # Load credentials from the CURRENT env file (not the backup one)
    # We need current credentials to connect to the running database
    local db_name db_user db_pass db_host db_port pg_mode database_url
    if [ -f "$ENV_FILE" ]; then
        db_name=$(grep -E "^DB_NAME=" "$ENV_FILE" | cut -d= -f2)
        db_user=$(grep -E "^DB_USER=" "$ENV_FILE" | cut -d= -f2)
        db_pass=$(grep -E "^DB_PASSWORD=" "$ENV_FILE" | cut -d= -f2)
        db_host=$(grep -E "^DB_HOST=" "$ENV_FILE" | cut -d= -f2)
        db_port=$(grep -E "^DB_PORT=" "$ENV_FILE" | cut -d= -f2)
        pg_mode=$(grep -E "^PG_MODE=" "$ENV_FILE" | cut -d= -f2)
        database_url=$(grep -E "^DATABASE_URL=" "$ENV_FILE" | cut -d= -f2-)
    fi

    db_name="${db_name:-ritapi_v_sentinel}"
    db_user="${db_user:-ritapi}"
    db_host="${db_host:-127.0.0.1}"
    db_port="${db_port:-5432}"

    if [ "$DRY_RUN" = true ]; then
        if [ "${pg_mode:-auto}" = "external" ] && [ -n "$database_url" ]; then
            print_info "[DRY RUN] Would restore database via DATABASE_URL from $dir/db_dump.sql"
        else
            print_info "[DRY RUN] Would drop and recreate '$db_name', then restore from $dir/db_dump.sql"
        fi
        return 0
    fi

    if [ "${pg_mode:-auto}" = "external" ] && [ -n "$database_url" ]; then
        # External DB: use psql with DATABASE_URL
        if psql "$database_url" < "$dir/db_dump.sql" >/dev/null 2>&1; then
            print_success "Database restored (external mode)"
        else
            print_error "Database restore failed (external mode)"
            return 1
        fi
    else
        # Local DB: drop and recreate, then restore
        print_info "Dropping and recreating database '$db_name'..."
        sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$db_name' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS $db_name;" >/dev/null 2>&1
        sudo -u postgres psql -c "CREATE DATABASE $db_name OWNER $db_user;" >/dev/null 2>&1
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;" >/dev/null 2>&1

        print_info "Restoring database from dump..."
        if PGPASSWORD="$db_pass" psql -h "$db_host" -p "$db_port" -U "$db_user" "$db_name" < "$dir/db_dump.sql" >/dev/null 2>&1; then
            print_success "Database restored successfully"
        else
            # Fallback: try as postgres user
            if sudo -u postgres psql "$db_name" < "$dir/db_dump.sql" >/dev/null 2>&1; then
                print_success "Database restored via peer auth"
            else
                print_error "Database restore failed"
                return 1
            fi
        fi
    fi
}

rollback_config() {
    local dir="$1"

    if [ "$SKIP_CONFIG" = true ]; then
        print_info "Skipping config restore (--skip-config)"
        return 0
    fi

    if [ ! -f "$dir/vsentinel.env" ]; then
        print_warning "No config backup found, skipping config restore"
        return 0
    fi

    print_info "Restoring configuration..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would restore: $dir/vsentinel.env -> $ENV_FILE"
        return 0
    fi

    # Backup current config before overwriting
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${ENV_FILE}.pre-rollback"
        print_info "Current config saved to ${ENV_FILE}.pre-rollback"
    fi

    cp "$dir/vsentinel.env" "$ENV_FILE"
    chown root:www-data "$ENV_FILE" 2>/dev/null || true
    chmod 0640 "$ENV_FILE"

    print_success "Configuration restored"
}

rollback_code() {
    local dir="$1"

    if [ "$SKIP_CODE" = true ]; then
        print_info "Skipping code restore (--skip-code)"
        return 0
    fi

    # Restore Django code
    if [ -f "$dir/ritapi_code.tar.gz" ]; then
        print_info "Restoring Django application code..."

        if [ "$DRY_RUN" = true ]; then
            print_info "[DRY RUN] Would extract: $dir/ritapi_code.tar.gz -> /opt/"
        else
            # Preserve venv (don't delete it, tar won't overwrite it since it was excluded)
            tar xzf "$dir/ritapi_code.tar.gz" -C /opt/ 2>/dev/null
            chown -R www-data:www-data "$DJANGO_PROJECT_DIR" 2>/dev/null || true
            chmod -R 755 "$DJANGO_PROJECT_DIR"
            print_success "Django code restored"
        fi
    else
        print_warning "No Django code backup found"
    fi

    # Restore MiniFW code
    if [ -f "$dir/minifw_code.tar.gz" ]; then
        print_info "Restoring MiniFW application code..."

        if [ "$DRY_RUN" = true ]; then
            print_info "[DRY RUN] Would extract: $dir/minifw_code.tar.gz -> /opt/"
        else
            tar xzf "$dir/minifw_code.tar.gz" -C /opt/ 2>/dev/null
            chown -R www-data:www-data "$MINIFW_AI_DIR" 2>/dev/null || true
            chmod -R 755 "$MINIFW_AI_DIR"
            print_success "MiniFW code restored"
        fi
    else
        print_warning "No MiniFW code backup found"
    fi
}

run_migrations() {
    print_info "Running Django migrations to match restored code..."

    local py="${DJANGO_PROJECT_DIR}/venv/bin/python"
    local manage="${DJANGO_PROJECT_DIR}/manage.py"

    if [ ! -f "$py" ] || [ ! -f "$manage" ]; then
        print_warning "Django manage.py or venv not found, skipping migrations"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would run: manage.py migrate --noinput"
        return 0
    fi

    if [ -f "$ENV_FILE" ]; then
        sudo -u www-data bash -c "set -a; source $ENV_FILE; set +a; cd $DJANGO_PROJECT_DIR; $py $manage migrate --noinput" 2>/dev/null || true
    else
        cd "$DJANGO_PROJECT_DIR"
        "$py" "$manage" migrate --noinput 2>/dev/null || true
    fi

    print_success "Migrations complete"
}

start_services() {
    print_info "Starting services..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would start: postgresql, redis-server, minifw-ai, ritapi-gunicorn"
        return 0
    fi

    systemctl start postgresql 2>/dev/null || true
    systemctl start redis-server 2>/dev/null || true
    systemctl start minifw-ai 2>/dev/null || true
    systemctl start ritapi-gunicorn 2>/dev/null || true

    # Wait for services to start
    sleep 3
    print_success "Services started"
}

verify_rollback() {
    print_info "Verifying rollback..."

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would verify: service status and HTTP health"
        return 0
    fi

    local errors=0

    # Check services
    for svc in postgresql redis-server minifw-ai ritapi-gunicorn; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            print_success "$svc is running"
        else
            print_warning "$svc is not running"
            errors=$((errors + 1))
        fi
    done

    # Check HTTP
    if command -v curl >/dev/null 2>&1; then
        if curl -fsS --max-time 10 http://127.0.0.1:8000/ >/dev/null 2>&1; then
            print_success "HTTP health check passed (200 on localhost:8000)"
        else
            print_warning "HTTP health check failed on localhost:8000"
            errors=$((errors + 1))
        fi
    fi

    if [ "$errors" -gt 0 ]; then
        print_warning "Rollback completed with $errors warning(s) - review service status"
    else
        print_success "All verification checks passed"
    fi
}

################################################################################
# Main
################################################################################

main() {
    # Must be root
    if [ "$EUID" -ne 0 ]; then
        print_error "Must be run as root (use sudo)"
        exit 1
    fi

    # List mode
    if [ "$LIST_ONLY" = true ]; then
        list_backups
        exit 0
    fi

    # Resolve backup directory
    if [ -z "$BACKUP_DIR" ]; then
        BACKUP_DIR=$(find_latest_backup)
        print_info "Using latest backup: $BACKUP_DIR"
    fi

    echo ""
    print_info "========================================"
    print_info "  V-Sentinel Rollback"
    print_info "========================================"
    echo ""

    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY RUN MODE - no changes will be made"
        print_warning "Use --confirm to execute the rollback"
        echo ""
    fi

    # Validate
    validate_backup "$BACKUP_DIR"

    if [ "$DRY_RUN" = true ]; then
        echo ""
        print_info "--- DRY RUN: showing planned actions ---"
        echo ""
    fi

    # Execute rollback steps
    stop_services
    rollback_database "$BACKUP_DIR"
    rollback_config "$BACKUP_DIR"
    rollback_code "$BACKUP_DIR"
    run_migrations
    start_services
    verify_rollback

    echo ""
    if [ "$DRY_RUN" = true ]; then
        print_info "========================================"
        print_info "  DRY RUN complete. No changes made."
        print_info "  Run with --confirm to execute."
        print_info "========================================"
    else
        print_success "========================================"
        print_success "  Rollback complete from: $(basename "$BACKUP_DIR")"
        print_success "========================================"
    fi
    echo ""
}

main
