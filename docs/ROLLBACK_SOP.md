# V-Sentinel Rollback Standard Operating Procedure (SOP)

**Version:** 1.0
**Last Updated:** February 10, 2026

---

## 1. Prerequisites

- **Root access** on the V-Sentinel host
- PostgreSQL client tools (`psql`, `pg_dump`) installed
- A valid backup created by `scripts/vsentinel_backup.sh` in `/var/backups/ritapi/`
- Services: `ritapi-gunicorn`, `minifw-ai`, `postgresql`, `redis-server`, `nginx`

### Verify Backup Exists

```bash
sudo bash scripts/vsentinel_rollback.sh --list
```

If no backups exist, rollback requires manual intervention (see Section 5).

---

## 2. Decision Matrix: Rollback vs. Fix-Forward

| Scenario | Recommended Action |
|---|---|
| Database migration failed mid-way | **Rollback** — partial migrations leave schema in unknown state |
| New code has a bug in one view | **Fix-forward** — deploy a patch, faster than full rollback |
| RBAC permissions broken for all users | **Rollback** — DB restore is the quickest path to restore access |
| MiniFW-AI service won't start after upgrade | **Rollback code** — restore previous code with `--skip-db` |
| Config change broke authentication | **Rollback config** — restore env file with `--skip-db --skip-code` |
| Data corruption in database | **Rollback** — full DB restore required |
| Minor UI regression | **Fix-forward** — rollback is disproportionate |
| Multiple interacting failures | **Rollback** — too many unknowns to fix-forward safely |

---

## 3. Quick Rollback (Automated)

### Dry Run (default — shows what would happen without making changes)

```bash
sudo bash scripts/vsentinel_rollback.sh
```

### Execute Rollback with Latest Backup

```bash
sudo bash scripts/vsentinel_rollback.sh --confirm
```

### Execute Rollback with Specific Backup

```bash
sudo bash scripts/vsentinel_rollback.sh /var/backups/ritapi/backup_20260210_143022 --confirm
```

### Selective Rollback

```bash
# Database only (skip code and config)
sudo bash scripts/vsentinel_rollback.sh --skip-code --skip-config --confirm

# Code only (skip database and config)
sudo bash scripts/vsentinel_rollback.sh --skip-db --skip-config --confirm

# Config only
sudo bash scripts/vsentinel_rollback.sh --skip-db --skip-code --confirm
```

---

## 4. Manual Rollback Steps

Use these when the automated script is unavailable or when you need fine-grained control.

### 4.1 Stop Application Services

```bash
sudo systemctl stop ritapi-gunicorn
sudo systemctl stop minifw-ai
# Leave Nginx running (serves maintenance page if configured)
```

### 4.2 Database Rollback

**Option A: Full restore from backup dump**

```bash
# Terminate active connections
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='ritapi_v_sentinel' AND pid <> pg_backend_pid();"

# Drop and recreate
sudo -u postgres psql -c "DROP DATABASE IF EXISTS ritapi_v_sentinel;"
sudo -u postgres psql -c "CREATE DATABASE ritapi_v_sentinel OWNER ritapi;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ritapi_v_sentinel TO ritapi;"

# Restore
sudo -u postgres psql ritapi_v_sentinel < /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/db_dump.sql
```

**Option B: Targeted migration rollback (single app)**

```bash
cd /opt/ritapi_v_sentinel
source /etc/ritapi/vsentinel.env

# Check current migration state
sudo -u www-data ./venv/bin/python manage.py showmigrations minifw

# Roll back minifw to a specific migration
sudo -u www-data ./venv/bin/python manage.py migrate minifw 0003_previous_migration

# Roll back all migrations for an app (use with caution)
sudo -u www-data ./venv/bin/python manage.py migrate minifw zero
```

### 4.3 RBAC Rollback

RBAC state (UserProfile roles, permissions) is stored in the `authentication_userprofile` table within the main database. A full database restore (4.2 Option A) automatically restores all RBAC state. There are no separate permission tables to restore.

For targeted RBAC rollback without full DB restore:

```bash
# Export current RBAC state first (for safety)
sudo -u postgres psql ritapi_v_sentinel -c "COPY authentication_userprofile TO '/tmp/userprofile_current.csv' CSV HEADER;"

# Restore RBAC from a backup's DB dump (extract just the table)
sudo -u postgres pg_restore --data-only --table=authentication_userprofile \
    /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/db_dump.sql 2>/dev/null \
    || echo "If pg_restore fails (plain SQL dump), use psql approach below"

# Alternative: manually restore from the SQL dump
# 1. Extract INSERT statements for the userprofile table from db_dump.sql
# 2. Truncate and re-insert
```

### 4.4 Dashboard/Code Rollback

```bash
# Restore Django code
cd /opt
sudo tar xzf /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/ritapi_code.tar.gz
sudo chown -R www-data:www-data /opt/ritapi_v_sentinel
sudo chmod -R 755 /opt/ritapi_v_sentinel

# Restore MiniFW code
sudo tar xzf /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/minifw_code.tar.gz
sudo chown -R www-data:www-data /opt/minifw_ai
sudo chmod -R 755 /opt/minifw_ai

# Run migrations to match restored code
cd /opt/ritapi_v_sentinel
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; ./venv/bin/python manage.py migrate --noinput"
```

### 4.5 Config Rollback

```bash
# Backup current config first
sudo cp /etc/ritapi/vsentinel.env /etc/ritapi/vsentinel.env.pre-rollback

# Restore from backup
sudo cp /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/vsentinel.env /etc/ritapi/vsentinel.env
sudo chown root:www-data /etc/ritapi/vsentinel.env
sudo chmod 0640 /etc/ritapi/vsentinel.env
```

### 4.6 Restart Services

```bash
sudo systemctl start postgresql
sudo systemctl start redis-server
sudo systemctl start minifw-ai
sudo systemctl start ritapi-gunicorn
sudo systemctl restart nginx
```

---

## 5. Verification Checkpoints

Run these checks after any rollback:

```bash
# 1. Service status
sudo systemctl is-active postgresql redis-server minifw-ai ritapi-gunicorn nginx

# 2. Django system check
cd /opt/ritapi_v_sentinel
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; ./venv/bin/python manage.py check"

# 3. HTTP health
curl -fsS http://127.0.0.1:8000/ && echo "OK" || echo "FAIL"

# 4. Database connectivity
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; cd /opt/ritapi_v_sentinel; ./venv/bin/python manage.py dbshell" <<< "SELECT 1;"

# 5. Migration consistency
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; cd /opt/ritapi_v_sentinel; ./venv/bin/python manage.py showmigrations" | grep '\[ \]'
# No unapplied migrations should appear

# 6. MiniFW-AI service
sudo journalctl -u minifw-ai --since "5 minutes ago" --no-pager | tail -5

# 7. Self-test (if available)
sudo bash scripts/vsentinel_selftest.sh
```

---

## 6. Migration-Specific Rollback

Django migrations in this project are auto-reversible (no custom `RunPython` operations). You can roll back individual apps to specific migration points.

### List Applied Migrations

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; ./venv/bin/python manage.py showmigrations"
```

### Roll Back a Single App

```bash
# Roll back 'minifw' to migration 0002
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; ./venv/bin/python manage.py migrate minifw 0002"

# Roll back 'authentication' completely
sudo -u www-data bash -c "set -a; source /etc/ritapi/vsentinel.env; set +a; ./venv/bin/python manage.py migrate authentication zero"
```

### Roll Back All Apps to a Point in Time

Use the `migration_state.txt` file from a backup to identify which migration each app should be at, then run targeted migrate commands for each app.

---

## 7. Known Risks

### 7.1 minifw_fixed Overlay Sync

The `scripts/minifw_fixed/` overlay is applied during installation by `apply_minifw_crud_fix()`. After a code rollback, the overlay files in the deployed Django app (`/opt/ritapi_v_sentinel/minifw/`) will match the backup state. However, if you later re-run the installer, the overlay from the current source tree will be re-applied. Ensure the source `scripts/minifw_fixed/` matches the deployed `minifw/` code.

### 7.2 External Database (PG_MODE=external)

If using an external/managed database (RDS, Cloud SQL), the rollback script uses `psql` with `DATABASE_URL`. Ensure:
- Network access to the external DB from the host
- The database user has `DROP DATABASE` / `CREATE DATABASE` privileges
- Consider using the managed service's snapshot/restore instead

### 7.3 Data Loss in New Tables

Rolling back the database to a pre-upgrade state will lose any data written to tables created by the upgrade's migrations. This includes:
- New records in newly created tables
- Data in new columns added by migrations

### 7.4 Secrets Regeneration

If rolling back config (`vsentinel.env`), the restored secrets (DJANGO_SECRET_KEY, MINIFW_SECRET_KEY) will differ from any currently active sessions. All active user sessions will be invalidated. This is expected and acceptable.

### 7.5 venv Compatibility

Code rollback restores application code but not the Python virtual environment. If the old code requires different package versions, you may need to:

```bash
cd /opt/ritapi_v_sentinel
./venv/bin/pip install -r requirements.txt
```

---

## 8. Recovery Procedures (If Rollback Fails)

### 8.1 Database Restore Fails

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check disk space
df -h /var/lib/postgresql

# Try restoring as postgres superuser
sudo -u postgres psql ritapi_v_sentinel < /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/db_dump.sql

# If DB is completely broken, recreate from scratch
sudo -u postgres psql -c "DROP DATABASE IF EXISTS ritapi_v_sentinel;"
sudo -u postgres psql -c "CREATE DATABASE ritapi_v_sentinel OWNER ritapi;"
sudo -u postgres psql ritapi_v_sentinel < /var/backups/ritapi/backup_XXXXXXXX_XXXXXX/db_dump.sql
```

### 8.2 Services Won't Start After Rollback

```bash
# Check logs
sudo journalctl -u ritapi-gunicorn --since "10 minutes ago" --no-pager
sudo journalctl -u minifw-ai --since "10 minutes ago" --no-pager

# Verify permissions
sudo chown -R www-data:www-data /opt/ritapi_v_sentinel
sudo chown -R www-data:www-data /opt/minifw_ai

# Verify venv is intact
/opt/ritapi_v_sentinel/venv/bin/python -c "import django; print(django.get_version())"

# Rebuild venv if corrupted
cd /opt/ritapi_v_sentinel
python3 -m venv venv --clear
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install gunicorn
```

### 8.3 Complete Recovery (Last Resort)

If rollback fails completely and the system is unrecoverable:

```bash
# Full reinstall from source
sudo ./install.sh install
```

This performs a clean installation from the source tree. The database will be recreated (data loss), but the system will be functional.

---

## 9. Creating a Manual Backup (Before Risky Changes)

If the automated backup hasn't run, create one manually:

```bash
sudo bash scripts/vsentinel_backup.sh

# Verify it was created
sudo bash scripts/vsentinel_rollback.sh --list
```

For database-only backup:

```bash
sudo bash scripts/vsentinel_backup.sh --db-only
```
