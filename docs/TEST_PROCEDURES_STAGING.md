# Staging Test Procedures

Manual test procedures for components that cannot be unit-tested (bash installer functions, operational rollback scripts).

**Last Updated:** February 11, 2026

---

## 1. PostgreSQL Installer Tests

These test the `detect_postgresql()` and `setup_postgresql()` functions in `install.sh`.

### Prerequisites
- Staging VM (Ubuntu 22.04+ or Debian 12+)
- Root/sudo access
- Snapshot capability (to restore between tests)

### 1.1 Clean Install (No PostgreSQL)

**Setup:** Fresh VM with no PostgreSQL installed.

```bash
# Verify no PG present
which psql        # Should not exist
pg_isready 2>&1   # Should fail
```

**Execute:**
```bash
sudo ./install.sh install
```

**Verify:**
- [ ] PostgreSQL installed and running: `systemctl is-active postgresql`
- [ ] DB user created: `sudo -u postgres psql -c "\du" | grep vsentinel`
- [ ] Database created: `sudo -u postgres psql -l | grep vsentinel`
- [ ] Django migrations applied: `cd /opt/ritapi_v_sentinel && source venv/bin/activate && python manage.py showmigrations | grep -v "\[ \]"`
- [ ] `deployment_state.json` written with correct DB info

### 1.2 ABORT Mode (Existing PostgreSQL)

**Setup:** VM with PostgreSQL already running. Set `PG_MODE=abort` in env.

```bash
echo "PG_MODE=abort" >> /etc/ritapi/vsentinel.env
```

**Execute:**
```bash
sudo ./install.sh install
```

**Verify:**
- [ ] Installer exits with clear error message mentioning existing PostgreSQL
- [ ] No new databases or users created
- [ ] Existing PostgreSQL data unchanged: `sudo -u postgres psql -l` (compare before/after)
- [ ] Exit code is non-zero

### 1.3 REUSE Mode (Existing PostgreSQL)

**Setup:** VM with PostgreSQL running. Set `PG_MODE=reuse`.

```bash
echo "PG_MODE=reuse" >> /etc/ritapi/vsentinel.env
```

**Execute:**
```bash
sudo ./install.sh install
```

**Verify:**
- [ ] Installer connects to existing PostgreSQL (no new cluster created)
- [ ] DB user `vsentinel` created if missing
- [ ] Database `vsentinel` created if missing
- [ ] Migrations run successfully
- [ ] Existing data in other databases untouched

### 1.4 EXTERNAL_DB Mode

**Setup:** Remote PostgreSQL accessible from staging VM. Set env vars:

```bash
cat >> /etc/ritapi/vsentinel.env <<EOF
PG_MODE=external
DATABASE_URL=postgres://vsentinel:password@remote-host:5432/vsentinel
EOF
```

**Execute:**
```bash
sudo ./install.sh install
```

**Verify:**
- [ ] No local PostgreSQL started or installed
- [ ] Django connects to remote database: check `settings.py` DATABASES
- [ ] Migrations applied on remote: `python manage.py showmigrations`
- [ ] Dashboard loads with remote DB data

---

## 2. Rollback Tests

These test `scripts/vsentinel_backup.sh` and `scripts/vsentinel_rollback.sh`.

### Prerequisites
- Staging VM with V-Sentinel fully installed
- Known test data in database (create test users, audit entries)
- VM snapshot before starting

### 2.1 Full Rollback

**Setup:** Working installation with test data.

```bash
# Record pre-upgrade state
sudo -u postgres pg_dump vsentinel > /tmp/pre_upgrade_dump.sql
md5sum /opt/ritapi_v_sentinel/manage.py > /tmp/pre_upgrade_checksums.txt
md5sum /etc/ritapi/vsentinel.env >> /tmp/pre_upgrade_checksums.txt
```

**Execute:**
```bash
# Create backup
sudo bash scripts/vsentinel_backup.sh

# Simulate upgrade (modify a file to prove rollback restores it)
echo "# UPGRADE MARKER" | sudo tee -a /opt/ritapi_v_sentinel/manage.py

# Rollback
sudo bash scripts/vsentinel_rollback.sh
```

**Verify:**
- [ ] Code restored: `md5sum /opt/ritapi_v_sentinel/manage.py` matches pre-upgrade
- [ ] Config restored: `md5sum /etc/ritapi/vsentinel.env` matches pre-upgrade
- [ ] Database restored: `sudo -u postgres pg_dump vsentinel | diff - /tmp/pre_upgrade_dump.sql`
- [ ] Services running: `systemctl is-active ritapi-gunicorn minifw-ai`
- [ ] Dashboard accessible and showing correct data

### 2.2 Selective Rollback: Code + Config Only (--skip-db)

**Execute:**
```bash
sudo bash scripts/vsentinel_backup.sh
echo "# UPGRADE MARKER" | sudo tee -a /opt/ritapi_v_sentinel/manage.py
sudo bash scripts/vsentinel_rollback.sh --skip-db
```

**Verify:**
- [ ] Code files restored (UPGRADE MARKER removed)
- [ ] Config files restored
- [ ] Database NOT rolled back (new data still present)
- [ ] Services restart successfully

### 2.3 Selective Rollback: Database Only (--skip-code)

**Execute:**
```bash
sudo bash scripts/vsentinel_backup.sh
# Add test data to DB
sudo -u postgres psql vsentinel -c "INSERT INTO auth_user (username, password, is_superuser, is_staff, is_active, date_joined) VALUES ('rollback_test', 'x', false, false, true, now());"
sudo bash scripts/vsentinel_rollback.sh --skip-code
```

**Verify:**
- [ ] Database rolled back: `sudo -u postgres psql vsentinel -c "SELECT username FROM auth_user WHERE username='rollback_test';"` returns 0 rows
- [ ] Code files unchanged
- [ ] Services restart successfully

### 2.4 Failure Recovery

**Setup:** Begin an install, then interrupt it mid-way.

```bash
sudo bash scripts/vsentinel_backup.sh

# Start install and kill after 10 seconds
sudo timeout 10 ./install.sh install || true

# Attempt rollback
sudo bash scripts/vsentinel_rollback.sh
```

**Verify:**
- [ ] Rollback completes without errors
- [ ] System returns to pre-upgrade state
- [ ] All services start: `sudo ./install.sh status`
- [ ] Dashboard accessible
- [ ] No orphaned processes or lock files

---

## 3. Test Execution Checklist

| Test | Executor | Date | Pass/Fail | Notes |
|------|----------|------|-----------|-------|
| PG Clean Install | | | | |
| PG ABORT Mode | | | | |
| PG REUSE Mode | | | | |
| PG EXTERNAL_DB Mode | | | | |
| Full Rollback | | | | |
| Selective --skip-db | | | | |
| Selective --skip-code | | | | |
| Failure Recovery | | | | |

---

**Document Type:** Staging Test Procedure
**Applies To:** install.sh, vsentinel_backup.sh, vsentinel_rollback.sh
