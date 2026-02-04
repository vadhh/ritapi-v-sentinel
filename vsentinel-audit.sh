#!/usr/bin/env bash
# v-sentinel integration audit checklist
# Purpose: detect known integration mismatches between RitAPI (Django) and MiniFW-AI.
# Safe: read-only (except it may run harmless commands like systemctl show).

set -u

RED='\033[0;31m'
YEL='\033[0;33m'
GRN='\033[0;32m'
BLU='\033[0;34m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() { echo -e "${GRN}[PASS]${NC} $*"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }
warn() { echo -e "${YEL}[WARN]${NC} $*"; WARN_COUNT=$((WARN_COUNT+1)); }
info() { echo -e "${BLU}[INFO]${NC} $*"; }

hr() { echo "--------------------------------------------------------------------------------"; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

# ---- Defaults (override via env if needed) ----
RITAPI_DIR="${RITAPI_DIR:-/opt/ritapi_v_sentinel}"
MINIFW_DIR="${MINIFW_DIR:-/opt/minifw_ai}"
MINIFW_POLICY="${MINIFW_POLICY:-$MINIFW_DIR/config/policy.json}"
VSENTINEL_ENV="${VSENTINEL_ENV:-/etc/ritapi/vsentinel.env}"

MINIFW_SERVICE="${MINIFW_SERVICE:-minifw-ai}"
RITAPI_SERVICE="${RITAPI_SERVICE:-ritapi-gunicorn}"

# --- helpers ---
as_root_hint() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    warn "Run as root for best visibility: sudo $0"
  fi
}

section() {
  hr
  echo -e "${BLU}## $*${NC}"
  hr
}

read_unit_prop() {
  local unit="$1" prop="$2"
  systemctl show "$unit" -p "$prop" --value 2>/dev/null || true
}

check_file() {
  local path="$1" desc="$2"
  if [[ -e "$path" ]]; then
    pass "$desc exists: $path"
  else
    fail "$desc missing: $path"
  fi
}

check_dir() {
  local path="$1" desc="$2"
  if [[ -d "$path" ]]; then
    pass "$desc dir exists: $path"
  else
    fail "$desc dir missing: $path"
  fi
}

# ---- Start ----
as_root_hint

echo "v-sentinel integration audit"
echo "Host: $(hostname) | Date: $(date -Is)"
echo "RitAPI: $RITAPI_DIR"
echo "MiniFW: $MINIFW_DIR"
echo

# 1) Basic layout
section "Filesystem layout"
check_dir "$RITAPI_DIR" "RitAPI install root"
check_file "$RITAPI_DIR/manage.py" "Django manage.py"
check_dir "$RITAPI_DIR/venv" "RitAPI venv"
check_dir "$MINIFW_DIR" "MiniFW install root"
check_dir "$MINIFW_DIR/venv" "MiniFW venv"
check_dir "$MINIFW_DIR/app" "MiniFW app dir"
check_file "$MINIFW_POLICY" "MiniFW policy file"
check_file "$VSENTINEL_ENV" "V-Sentinel env file"

# 2) systemd unit correctness for MiniFW
section "Systemd: MiniFW service unit sanity"
if systemctl list-unit-files | grep -q "^${MINIFW_SERVICE}\.service"; then
  pass "Unit file registered: ${MINIFW_SERVICE}.service"
else
  fail "Unit file not registered: ${MINIFW_SERVICE}.service"
fi

MINIFW_EXEC="$(read_unit_prop "${MINIFW_SERVICE}.service" ExecStart)"
MINIFW_USER="$(read_unit_prop "${MINIFW_SERVICE}.service" User)"
MINIFW_ENV="$(read_unit_prop "${MINIFW_SERVICE}.service" Environment)"
MINIFW_WD="$(read_unit_prop "${MINIFW_SERVICE}.service" WorkingDirectory)"
MINIFW_STATUS="$(systemctl is-active "${MINIFW_SERVICE}.service" 2>/dev/null || true)"

info "ExecStart: ${MINIFW_EXEC:-<unknown>}"
info "User: ${MINIFW_USER:-<unknown>}"
info "WorkingDirectory: ${MINIFW_WD:-<unknown>}"
info "Active: ${MINIFW_STATUS:-<unknown>}"

# Known mismatch: unit expects /opt/minifw_ai/run_minifw.sh but installer might not have created it
if echo "$MINIFW_EXEC" | grep -q "/opt/minifw_ai/run_minifw.sh"; then
  if [[ -x "$MINIFW_DIR/run_minifw.sh" ]]; then
    pass "run_minifw.sh exists and executable (unit references it)"
  else
    fail "Unit references run_minifw.sh but file missing or not executable: $MINIFW_DIR/run_minifw.sh"
    warn "Likely you copied the unit but never ran scripts that generate run_minifw.sh (install_systemd.sh)."
  fi
else
  warn "Unit does not reference run_minifw.sh (may be installer fallback)."
fi

# Known mismatch: python -m minifw_ai needs PYTHONPATH=/opt/minifw_ai/app
if echo "$MINIFW_EXEC" | grep -q "python.*-m[[:space:]]\+minifw_ai"; then
  if echo "$MINIFW_ENV" | grep -q "PYTHONPATH=.*$MINIFW_DIR/app"; then
    pass "PYTHONPATH is set for 'python -m minifw_ai' execution"
  else
    fail "ExecStart uses 'python -m minifw_ai' but PYTHONPATH does not include '$MINIFW_DIR/app'"
    warn "Fix by setting Environment=PYTHONPATH=$MINIFW_DIR/app in the unit (or use absolute module path)."
  fi
fi

# Known mismatch: PATH excludes /usr/sbin => nft not found
if echo "$MINIFW_ENV" | grep -q 'PATH='; then
  # Extract PATH var from Environment= (systemctl show prints space-separated entries)
  # We just check if /usr/sbin appears anywhere.
  if echo "$MINIFW_ENV" | grep -q "/usr/sbin"; then
    pass "Service PATH includes /usr/sbin (nft likely discoverable)"
  else
    fail "Service PATH does not include /usr/sbin (common reason for 'nft not found')"
    warn "Add Environment=\"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\" to the unit."
  fi
else
  warn "Service unit has no explicit PATH. systemd default may exclude /usr/sbin."
fi

# 3) systemd: RitAPI service sanity
section "Systemd: RitAPI (gunicorn) sanity"
if systemctl list-unit-files | grep -q "^${RITAPI_SERVICE}\.service"; then
  pass "Unit file registered: ${RITAPI_SERVICE}.service"
else
  warn "Unit file not registered: ${RITAPI_SERVICE}.service (dashboard may be running differently)"
fi
RITAPI_STATUS="$(systemctl is-active "${RITAPI_SERVICE}.service" 2>/dev/null || true)"
info "Active: ${RITAPI_STATUS:-<unknown>}"

# Known mismatch: Type=notify without notify support
RITAPI_TYPE="$(read_unit_prop "${RITAPI_SERVICE}.service" Type)"
if [[ -n "${RITAPI_TYPE:-}" ]]; then
  info "Service Type: $RITAPI_TYPE"
  if [[ "$RITAPI_TYPE" == "notify" ]]; then
    warn "RitAPI service uses Type=notify. If gunicorn isn't wired for sd_notify, start may fail."
    warn "Prefer Type=simple unless you're explicitly using systemd notify support."
  else
    pass "RitAPI service type is not notify ($RITAPI_TYPE)"
  fi
else
  warn "Could not read RitAPI service Type (unit may not exist)."
fi

# 4) nftables / ipset readiness
section "Firewall dependencies"
if have_cmd nft; then
  pass "nft command present: $(command -v nft)"
else
  fail "nft command missing (install nftables)"
fi

if have_cmd ipset; then
  pass "ipset command present: $(command -v ipset)"
else
  fail "ipset command missing (install ipset)"
fi

# Check expected ipset set
if have_cmd ipset; then
  if ipset list -n 2>/dev/null | grep -qx "minifw_block_v4"; then
    pass "ipset set exists: minifw_block_v4"
  else
    warn "ipset set not found: minifw_block_v4 (MiniFW may create dynamically or failed earlier)"
  fi
fi

# Check nft ruleset references ipset (optional, but informative)
if have_cmd nft; then
  if nft list ruleset 2>/dev/null | grep -q "minifw_block_v4"; then
    pass "nft ruleset references minifw_block_v4 (kernel enforcement likely active)"
  else
    warn "nft ruleset does not reference minifw_block_v4 (enforcement may not be wired)"
    warn "Creating an ipset alone does nothing unless nft rules drop traffic using it."
  fi
fi

# 5) Policy schema drift checks
section "Config contract checks (policy.json schema drift)"
if [[ -f "$MINIFW_POLICY" ]]; then
  if have_cmd python3; then
    # parse keys safely; no jq dependency
    python3 - <<'PY' "$MINIFW_POLICY"
import json, sys
p=sys.argv[1]
try:
    data=json.load(open(p,'r',encoding='utf-8'))
except Exception as e:
    print(f"[FAIL] policy.json is not valid JSON: {e}")
    sys.exit(2)

def has(path):
    cur=data
    for k in path:
        if not isinstance(cur, dict) or k not in cur: return False
        cur=cur[k]
    return True

checks = [
    (("enforcement","ipset_name"), "enforcement.ipset_name"),
    (("enforcement","ipset_name_v4"), "enforcement.ipset_name_v4"),
    (("enforcement","nft_path"), "enforcement.nft_path"),
    (("thresholds","block_score"), "thresholds.block_score"),
]
for keypath, label in checks:
    print(("[PASS]" if has(keypath) else "[WARN]"), label)
PY
    rc=$?
    if [[ $rc -eq 0 ]]; then
      pass "policy.json parsed successfully"
      warn "If you see enforcement.ipset_name but not enforcement.ipset_name_v4, UI/schema drift is likely."
    else
      fail "policy.json parse failed (see output above)"
    fi
  else
    warn "python3 not available to validate policy.json"
  fi
else
  fail "policy.json missing: $MINIFW_POLICY"
fi

# 6) Django ability to restart Minifw (privilege boundary)
section "Dashboard control-plane viability (can Django restart MiniFW?)"
# We check sudoers/polkit patterns without changing anything.
WEB_USER_CANDIDATES=("www-data" "nginx" "apache" "ritapi" "django")
FOUND_WEB_USER=""
for u in "${WEB_USER_CANDIDATES[@]}"; do
  if id "$u" >/dev/null 2>&1; then
    FOUND_WEB_USER="$u"
    break
  fi
done

if [[ -n "$FOUND_WEB_USER" ]]; then
  info "Detected web-like user: $FOUND_WEB_USER"
  if have_cmd sudo; then
    if sudo -n -u "$FOUND_WEB_USER" systemctl status "$MINIFW_SERVICE" >/dev/null 2>&1; then
      pass "Web user can run systemctl (sudo NOPASSWD or polkit configured)"
    else
      warn "Web user likely cannot run systemctl without password (dashboard restart buttons will fail)"
      warn "Fix options: polkit rule, sudoers NOPASSWD for specific commands, or separate agent IPC."
    fi
  else
    warn "sudo not installed; dashboard cannot elevate to restart services via sudo."
  fi
else
  warn "No standard web user found (www-data/nginx/apache/etc)."
fi

# 7) dnsmasq conflicts (common VM issue)
section "dnsmasq / resolver conflicts"
if systemctl list-unit-files | grep -q "^dnsmasq\.service"; then
  DNSMASQ_STATE="$(systemctl is-active dnsmasq 2>/dev/null || true)"
  info "dnsmasq active: ${DNSMASQ_STATE:-<unknown>}"
  if [[ "$DNSMASQ_STATE" != "active" ]]; then
    warn "dnsmasq not active. Many VMs use systemd-resolved which conflicts with dnsmasq on :53."
  else
    pass "dnsmasq is active"
  fi
else
  warn "dnsmasq service not installed (may be optional, or install failed)."
fi

if systemctl list-unit-files | grep -q "^systemd-resolved\.service"; then
  RESOLVED_STATE="$(systemctl is-active systemd-resolved 2>/dev/null || true)"
  info "systemd-resolved active: ${RESOLVED_STATE:-<unknown>}"
  if [[ "$RESOLVED_STATE" == "active" ]]; then
    warn "systemd-resolved is active. If you run dnsmasq on port 53, expect conflicts."
  fi
fi

# 8) MiniFW crash diagnostics (exit code 1 reasons)
section "MiniFW service status + last logs"
if systemctl list-unit-files | grep -q "^${MINIFW_SERVICE}\.service"; then
  systemctl --no-pager --full status "${MINIFW_SERVICE}.service" || true
  echo
  info "Last 120 lines of journal:"
  journalctl -u "${MINIFW_SERVICE}.service" -n 120 --no-pager || true
else
  warn "MiniFW service not installed; skipping logs."
fi

# 9) Dependency hazard checks (CPU / wheel mismatch indicators)
section "Python dependency hazards (CPU / wheel mismatch)"
# We can't perfectly detect X86_V2 support without deep probing, but we can flag known symptoms:
# - importing numpy/scipy failing
# - "illegal instruction" or baseline mismatch messages in logs
if [[ -x "$MINIFW_DIR/venv/bin/python" ]]; then
  "$MINIFW_DIR/venv/bin/python" - <<'PY'
import sys
def try_import(name):
    try:
        __import__(name)
        print(f"[PASS] import {name}")
    except Exception as e:
        print(f"[FAIL] import {name}: {e.__class__.__name__}: {e}")
for m in ("numpy","pandas","sklearn","scipy"):
    try_import(m)
PY
else
  warn "MiniFW venv python not found at $MINIFW_DIR/venv/bin/python"
fi

hr
echo "Summary: PASS=$PASS_COUNT WARN=$WARN_COUNT FAIL=$FAIL_COUNT"
hr

if [[ $FAIL_COUNT -gt 0 ]]; then
  echo -e "${RED}Result: NOT CLEAN${NC} (fix FAIL items first; WARN items are likely next blockers)"
else
  echo -e "${GRN}Result: CLEAN ENOUGH${NC} (no hard blockers detected; address WARN to harden)"
fi
