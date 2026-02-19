#!/usr/bin/env bash
# =============================================================================
# V-Sentinel Real-Time Demo Driver
# demos/demo_traffic_gen.sh
#
# Generates controlled traffic patterns to demonstrate MiniFW-AI detection
# across all 5 threat layers.
#
# Usage:
#   ./demos/demo_traffic_gen.sh --scenario A        # DNS denied domain
#   ./demos/demo_traffic_gen.sh --scenario B        # DNS burst flood
#   ./demos/demo_traffic_gen.sh --scenario C        # Hard gate (SYN flood)
#   ./demos/demo_traffic_gen.sh --scenario D        # Multi-layer combined
#   ./demos/demo_traffic_gen.sh --all               # Full demo sequence
#   ./demos/demo_traffic_gen.sh --setup-demo-policy # Lower thresholds for demo
#   ./demos/demo_traffic_gen.sh --restore-policy    # Restore original thresholds
#   ./demos/demo_traffic_gen.sh --check             # Check prerequisites
#
# Requirements:
#   - dig (dnsutils)        : sudo apt install dnsutils
#   - hping3 (Scenario C)   : sudo apt install hping3
#   - python3 (Scenario B)  : standard on all systems
#
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------

# Derive VM IP from installed production config (set by install.sh ensure_allowed_hosts).
# Falls back to ip route (same method install.sh uses), then hostname -I.
_detect_vm_ip() {
    local env_file="/etc/ritapi/vsentinel.env"
    local ip=""
    if [[ -f "$env_file" && -r "$env_file" ]]; then
        local hosts
        hosts=$(grep '^DJANGO_ALLOWED_HOSTS=' "$env_file" 2>/dev/null | cut -d= -f2)
        ip=$(echo "$hosts" | tr ',' '\n' | grep -vE '^(localhost|127\.|::1)$' | head -1)
    fi
    [[ -z "$ip" ]] && ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')
    [[ -z "$ip" ]] && ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    echo "${ip:-localhost}"
}

# Detect MINIFW_DNS_SOURCE from installed config, falling back to service inspection.
# Mirrors install.sh detect_dns_environment() logic so DNS_SERVER default is correct.
_detect_dns_source() {
    local env_file="/etc/ritapi/vsentinel.env"
    local source=""
    if [[ -f "$env_file" && -r "$env_file" ]]; then
        source=$(grep '^MINIFW_DNS_SOURCE=' "$env_file" 2>/dev/null | cut -d= -f2)
    fi
    # If env unreadable or still 'none', infer from running services
    if [[ -z "$source" || "$source" == "none" ]]; then
        if systemctl is-active --quiet systemd-resolved 2>/dev/null && \
           ss -tlnp 2>/dev/null | grep -q ':53 '; then
            source="journald"
        elif command -v dnsmasq &>/dev/null && \
             systemctl is-active --quiet dnsmasq 2>/dev/null; then
            source="file"
        else
            source="none"
        fi
    fi
    echo "$source"
}

DEMO_VM_IP="${DEMO_VM_IP:-$(_detect_vm_ip)}"
_MINIFW_DNS_SOURCE="${MINIFW_DNS_SOURCE:-$(_detect_dns_source)}"

# In journald mode queries must reach systemd-resolved's stub (127.0.0.53).
# In file/udp mode dnsmasq answers on 127.0.0.1.
if [[ "$_MINIFW_DNS_SOURCE" == "journald" ]]; then
    DNS_SERVER="${DNS_SERVER:-127.0.0.53}"
else
    DNS_SERVER="${DNS_SERVER:-127.0.0.1}"
fi

DJANGO_DASHBOARD_URL="${DJANGO_DASHBOARD_URL:-http://${DEMO_VM_IP}}"
MINIFW_EVENTS_URL="${MINIFW_EVENTS_URL:-${DJANGO_DASHBOARD_URL}/ops/minifw/events}"

# Policy file paths (production then dev fallback)
POLICY_JSON_PROD="/opt/minifw_ai/config/policy.json"
POLICY_JSON_DEV="$(dirname "$0")/../projects/minifw_ai_service/config/policy.json"
POLICY_JSON_BACKUP="/tmp/vsentinel_policy_demo_backup.json"

# Scoring reference (from policy.json defaults)
# dns_weight=41, burst_weight=10, asn_weight=15, sni_weight=34
# default segment: block_threshold=60, monitor_threshold=40
# student segment: block_threshold=40, monitor_threshold=20
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Colors ------------------------------------------------------------------
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# --- Helpers -----------------------------------------------------------------
info()    { echo -e "${BLUE}[INFO]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}  $*"; }
alert()   { echo -e "${RED}[BLOCK]${RESET} $*"; }
header()  { echo -e "\n${BOLD}${CYAN}=== $* ===${RESET}\n"; }
pause()   {
    echo -e "\n${BOLD}${YELLOW}>>> PRESENTER PAUSE <<<${RESET}"
    echo -e "$*"
    echo -e "${YELLOW}Press [ENTER] to continue...${RESET}"
    read -r
}

detect_policy_file() {
    if [[ -f "$POLICY_JSON_PROD" ]]; then
        echo "$POLICY_JSON_PROD"
    elif [[ -f "$POLICY_JSON_DEV" ]]; then
        echo "$POLICY_JSON_DEV"
    else
        echo ""
    fi
}

# --- Prerequisites check -----------------------------------------------------
check_prereqs() {
    header "Prerequisites Check"
    local ok=true

    # dig
    if command -v dig &>/dev/null; then
        success "dig (dnsutils) found: $(dig -v 2>&1 | head -1)"
    else
        warn "dig not found — install: sudo apt install dnsutils"
        ok=false
    fi

    # python3
    if command -v python3 &>/dev/null; then
        success "python3 found: $(python3 --version)"
    else
        warn "python3 not found"
        ok=false
    fi

    # hping3 (optional, needed for Scenario C)
    if command -v hping3 &>/dev/null; then
        success "hping3 found (Scenario C available)"
    else
        warn "hping3 not found — Scenario C disabled. Install: sudo apt install hping3"
    fi

    # DNS reachability — varies by configured telemetry source
    info "DNS telemetry source: $_MINIFW_DNS_SOURCE  |  DNS server: $DNS_SERVER"
    case "$_MINIFW_DNS_SOURCE" in
        journald)
            if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
                success "systemd-resolved is active (journald DNS collection enabled)"
                # Debug logging must be enabled or resolved emits no query-level messages
                local dropin="/etc/systemd/system/systemd-resolved.service.d/vsentinel-dns-logging.conf"
                if [[ -f "$dropin" ]]; then
                    success "Debug logging drop-in present ($dropin)"
                else
                    warn "Debug logging drop-in missing — resolved won't emit DNS query events"
                    warn "  Fix: sudo bash install.sh   (re-run installer) or manually:"
                    warn "  sudo mkdir -p /etc/systemd/system/systemd-resolved.service.d"
                    warn "  echo -e '[Service]\nEnvironment=\"SYSTEMD_LOG_LEVEL=debug\"' | sudo tee $dropin"
                    warn "  sudo systemctl daemon-reload && sudo systemctl restart systemd-resolved"
                    ok=false
                fi
                if dig +short +time=2 @"$DNS_SERVER" example.com A &>/dev/null; then
                    success "DNS resolver at $DNS_SERVER is answering queries"
                else
                    warn "DNS resolver at $DNS_SERVER not answering — demo queries may not generate events"
                fi
            else
                warn "systemd-resolved is not active — journald DNS collection unavailable"
                ok=false
            fi
            ;;
        file)
            if dig +short +time=2 @"$DNS_SERVER" example.com A &>/dev/null; then
                success "DNS server $DNS_SERVER is reachable (dnsmasq)"
            else
                warn "DNS server $DNS_SERVER unreachable — check dnsmasq is running"
                ok=false
            fi
            ;;
        udp)
            if dig +short +time=2 @"$DNS_SERVER" example.com A &>/dev/null; then
                success "DNS server $DNS_SERVER is reachable (UDP mode)"
            else
                warn "DNS server $DNS_SERVER unreachable — check UDP DNS source"
                ok=false
            fi
            ;;
        none|*)
            warn "DNS source is 'none' — Scenarios A/B/D will not generate MiniFW events"
            warn "Install dnsmasq or ensure systemd-resolved is active, then re-run install.sh"
            ;;
    esac

    # Policy file
    local pf
    pf="$(detect_policy_file)"
    if [[ -n "$pf" ]]; then
        success "Policy file found: $pf"
        local bt
        bt=$(python3 -c "import json; d=json.load(open('$pf')); print(d['segments']['default']['block_threshold'])")
        info "  Default segment block_threshold = $bt (need ≤41 for single-domain BLOCK demo)"
        if [[ "$bt" -le 41 ]]; then
            success "  Demo policy active (threshold lowered) — BLOCK events will fire on Scenario A"
        else
            warn "  Production threshold ($bt). Run --setup-demo-policy to lower for BLOCK demos."
            info "  Without it: Scenario A → MONITOR (score=41), Scenario B → MONITOR (score=51)."
        fi
    else
        warn "Policy file not found at either $POLICY_JSON_PROD or $POLICY_JSON_DEV"
        ok=false
    fi

    info "Resolved VM IP:  $DEMO_VM_IP (source: /etc/ritapi/vsentinel.env DJANGO_ALLOWED_HOSTS)"
    info "Dashboard URL:   $DJANGO_DASHBOARD_URL"

    # MiniFW events dashboard reachability (via Django)
    info "Testing MiniFW events viewer at $MINIFW_EVENTS_URL ..."
    if curl -sf --max-time 3 -o /dev/null -w "%{http_code}" "$MINIFW_EVENTS_URL/" 2>/dev/null | grep -qE "^(200|302|301)$"; then
        success "MiniFW events viewer reachable at $MINIFW_EVENTS_URL"
    else
        warn "MiniFW events not reachable at $MINIFW_EVENTS_URL"
        warn "  Check: sudo systemctl status ritapi-gunicorn.service minifw-ai.service"
    fi

    echo ""
    if $ok; then
        success "All required prerequisites satisfied."
    else
        warn "Some prerequisites missing. Check above. Scenarios may fail."
    fi
}

# --- Policy management -------------------------------------------------------
setup_demo_policy() {
    header "Setting Up Demo Policy (Lower Thresholds)"
    local pf
    pf="$(detect_policy_file)"
    if [[ -z "$pf" ]]; then
        echo "ERROR: policy.json not found. Cannot patch." >&2
        exit 1
    fi

    info "Backing up $pf → $POLICY_JSON_BACKUP"
    cp "$pf" "$POLICY_JSON_BACKUP"

    info "Patching default segment block_threshold: 60 → 35 (monitor_threshold: 40 → 20)"
    python3 - "$pf" <<'PYEOF'
import json, sys
path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
d['segments']['default']['block_threshold'] = 35
d['segments']['default']['monitor_threshold'] = 20
with open(path, 'w') as f:
    json.dump(d, f, indent=2)
print("  Patched: default block_threshold=35, monitor_threshold=20")
PYEOF

    success "Demo policy applied."
    warn "Run --restore-policy after the demo to restore production thresholds."
    info "NOTE: MiniFW-AI reads policy.json at runtime per-event — no restart needed."
}

restore_policy() {
    header "Restoring Production Policy"
    local pf
    pf="$(detect_policy_file)"
    if [[ -z "$pf" ]]; then
        echo "ERROR: policy.json not found." >&2
        exit 1
    fi

    if [[ -f "$POLICY_JSON_BACKUP" ]]; then
        cp "$POLICY_JSON_BACKUP" "$pf"
        rm -f "$POLICY_JSON_BACKUP"
        success "Policy restored from backup."
    else
        info "No backup found — writing standard production policy manually."
        python3 - "$pf" <<'PYEOF'
import json, sys
path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
d['segments']['default']['block_threshold'] = 60
d['segments']['default']['monitor_threshold'] = 40
with open(path, 'w') as f:
    json.dump(d, f, indent=2)
print("  Restored: default block_threshold=60, monitor_threshold=40")
PYEOF
        success "Policy restored to defaults."
    fi
}

# --- Scenario A: DNS Denied Domain -------------------------------------------
scenario_a() {
    header "Scenario A: DNS Denied Domain Query"
    cat <<EOF
WHAT HAPPENS:
  Query a domain matching the deny list (e.g., *.slot*, *.casino*)
  MiniFW-AI scores the source IP:
    dns_weight = 41 points
    With demo policy (threshold=35): action = BLOCK
    With production policy (threshold=60): action = MONITOR

DENIED DOMAINS (from deny_domains.txt):  *.casino*  |  *.slot*  |  *malware*  |  *.judionline*

EOF
    local domains=(
        "slots.example.com"
        "casino-demo.local"
        "malware-test.example.com"
        "judionline-staging.local"
    )

    pause "Open the Events Viewer: ${MINIFW_EVENTS_URL}/
Switch to another terminal and watch this run."

    info "Sending ${#domains[@]} queries to $DNS_SERVER for denied domains..."
    for domain in "${domains[@]}"; do
        echo -n "  dig @${DNS_SERVER} ${domain} A  →  "
        dig +short +time=2 @"$DNS_SERVER" "$domain" A &>/dev/null && echo "sent" || echo "no response (domain doesn't resolve — this is expected)"
        sleep 0.5
    done

    echo ""
    info "Sending 5 rapid queries for slots.example.com..."
    for i in $(seq 1 5); do
        dig +short +time=2 @"$DNS_SERVER" "slots${i}.example.com" A &>/dev/null || true
        sleep 0.3
    done

    pause "CHECK DASHBOARD:
  → Events Viewer should show new events with:
     domain=slots.example.com, reason=dns_denied_domain
     action=BLOCK (demo policy) or MONITOR (production policy)
     score=41

  → Run: sudo nft list set inet filter minifw_block_v4
     (should show your IP if policy threshold ≤ 41)"
}

# --- Scenario B: DNS Burst Flood ---------------------------------------------
scenario_b() {
    header "Scenario B: DNS Burst Flood (Rate Detection)"
    cat <<EOF
WHAT HAPPENS:
  Send 300+ DNS queries in under 60 seconds from one source IP.
  MiniFW-AI burst tracker crosses 240 queries/min threshold.
  burst_weight = +10 added to score.
    With denied domains + burst: score = 41+10 = 51 → MONITOR (default)
    With demo policy (threshold=35): score = 51 → BLOCK

  This demonstrates escalation: ALLOW → MONITOR → BLOCK

EOF
    pause "Open Events Viewer: ${MINIFW_EVENTS_URL}/
Watch for burst_behavior reason and score escalation."

    local count=0
    local start
    start=$(date +%s)
    local target=280
    local domain="slots-burst.example.com"

    info "Sending $target DNS queries for '$domain' — this takes ~45 seconds..."
    info "Target rate: >240/min (burst block threshold)"

    while [[ $count -lt $target ]]; do
        dig +short +time=1 @"$DNS_SERVER" "$domain" A &>/dev/null || true
        count=$((count + 1))

        if (( count % 50 == 0 )); then
            local elapsed=$(( $(date +%s) - start ))
            local rate=$(( count * 60 / (elapsed + 1) ))
            echo -e "  Sent: ${BOLD}${count}${RESET} queries | Elapsed: ${elapsed}s | Rate: ~${YELLOW}${rate}/min${RESET}"
        fi

        # Adaptive pacing: aim for ~280/min (slightly above 240 threshold)
        sleep 0.21
    done

    local total_elapsed=$(( $(date +%s) - start ))
    success "Burst complete: $count queries in ${total_elapsed}s (~$(( count * 60 / (total_elapsed + 1) ))/min)"

    pause "CHECK DASHBOARD:
  → Events Viewer: look for reason=burst_behavior, score should jump
  → Escalation sequence: earlier events show score=41, later show score=51+
  → If using demo policy: action should escalate from MONITOR to BLOCK"
}

# --- Scenario C: Hard Gate (SYN Flood) ---------------------------------------
scenario_c() {
    header "Scenario C: Hard Gate — SYN Flood (Immediate Block)"
    cat <<EOF
WHAT HAPPENS:
  Send a high-rate SYN flood (>300 packets/second).
  MiniFW-AI conntrack flow tracker detects burst_flood or pps_saturation.
  Hard threat gate fires: score = 100, reason = burst_flood/pps_saturation
  Action = BLOCK immediately — no scoring deliberation.

  This is the most dramatic scenario.

REQUIREMENT: hping3 must be installed and run with sudo.
  Install: sudo apt install hping3

EOF
    if ! command -v hping3 &>/dev/null; then
        warn "hping3 not found. Skipping Scenario C."
        info "Install with: sudo apt install hping3"
        return 0
    fi

    if [[ $EUID -ne 0 ]]; then
        warn "hping3 requires root. Re-run this scenario with sudo:"
        echo "  sudo bash demos/demo_traffic_gen.sh --scenario C"
        return 0
    fi

    pause "Open Events Viewer: ${MINIFW_EVENTS_URL}/
This will launch a 10-second SYN flood to $DEMO_VM_IP port 80.
Watch for score=100, reason=burst_flood, action=BLOCK."

    warn "Starting 10-second SYN flood to $DEMO_VM_IP:80..."
    info "(hping3 -S -p 80 --faster --count 3000 $DEMO_VM_IP)"

    # --faster = ~200pps; we also add --flood for maximum rate
    # Limit to 3000 packets or 10 seconds, whichever comes first
    timeout 10 hping3 -S -p 80 --faster "$DEMO_VM_IP" -c 3000 2>&1 | tail -5 || true

    success "SYN flood complete."

    pause "CHECK DASHBOARD:
  → Events Viewer: score=100, reason includes pps_saturation or burst_flood
  → hard_threat_gate_override in reasons list
  → action=BLOCK even if dns_denied=false (hard gate bypasses normal scoring)
  → Run: sudo nft list set inet filter minifw_block_v4 | grep $DEMO_VM_IP"
}

# --- Scenario D: Multi-Layer Combined ----------------------------------------
scenario_d() {
    header "Scenario D: Multi-Layer Combined Attack"
    cat <<EOF
WHAT HAPPENS:
  Trigger DNS denied domain + burst simultaneously.
  Demonstrates how the scoring pipeline aggregates multiple signals.

  dns_weight(41) + burst_weight(10) = 51 total score
  → MONITOR in default segment (threshold=60)
  → BLOCK in student segment (threshold=40) or with demo policy

EOF
    pause "Open Events Viewer: ${MINIFW_EVENTS_URL}/
Watch for multiple reasons on a single event."

    info "Phase 1: Querying denied domains while ramping up rate..."

    # Run DNS flood in background with denied domains
    local flood_pids=()
    for domain in "slots-multi.example.com" "casino-multi.example.com" "malware-multi.example.com"; do
        (
            for i in $(seq 1 80); do
                dig +short +time=1 @"$DNS_SERVER" "$domain" A &>/dev/null || true
                sleep 0.22
            done
        ) &
        flood_pids+=($!)
    done

    info "Phase 2: All 3 denied domains querying concurrently (~240+/min combined)..."
    info "Waiting for burst threshold to be crossed..."

    local countdown=20
    while [[ $countdown -gt 0 ]]; do
        echo -ne "  ${YELLOW}$countdown seconds remaining...${RESET}\r"
        sleep 1
        countdown=$((countdown - 1))
    done
    echo ""

    for pid in "${flood_pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    success "Multi-layer scenario complete."
    pause "CHECK DASHBOARD:
  → Events: multiple reason codes per event (dns_denied_domain + burst_behavior)
  → Score should show cumulative weighting (51+)
  → Compare with Scenario A (single reason, score=41)"
}

# --- Show blocked IPs --------------------------------------------------------
show_blocked_ips() {
    header "Current nftables Block Set"
    info "Running: sudo nft list set inet filter minifw_block_v4"
    echo ""
    if command -v nft &>/dev/null; then
        sudo nft list set inet filter minifw_block_v4 2>/dev/null || \
            warn "nft command failed — check if nftables is running and set exists"
    else
        warn "nft not found on this system"
    fi
    echo ""
    info "Django Dashboard blocked IPs: ${DJANGO_DASHBOARD_URL}/blocking/"
}

# --- Full demo sequence -------------------------------------------------------
run_all() {
    header "V-Sentinel Full Demo Sequence"
    cat <<EOF
  This will run all demo scenarios in sequence.
  Each scenario pauses for presenter narration.

  VM IP:          $DEMO_VM_IP
  DNS Server:     $DNS_SERVER
  MiniFW Events:  $MINIFW_EVENTS_URL/
  Django Dash:    $DJANGO_DASHBOARD_URL

EOF
    pause "Confirm demo environment:
  1. MiniFW admin tab open: ${MINIFW_EVENTS_URL}/
  2. Django dashboard tab open: ${DJANGO_DASHBOARD_URL}/blocking/
  3. Terminal 2 ready for: sudo nft list set inet filter minifw_block_v4
  4. Policy mode: run --setup-demo-policy first for BLOCK events"

    scenario_a
    scenario_b
    scenario_d
    scenario_c
    show_blocked_ips

    header "Demo Complete"
    success "All scenarios executed."
    info "Remember to run: ./demos/demo_traffic_gen.sh --restore-policy"
    info "Also clear nftables block set if needed:"
    echo "  sudo nft flush set inet filter minifw_block_v4"
}

# --- Entry point -------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 [OPTION]

Options:
  --scenario A      DNS denied domain query
  --scenario B      DNS burst flood (>240/min)
  --scenario C      Hard gate: SYN flood (requires sudo + hping3)
  --scenario D      Multi-layer combined attack
  --all             Full demo sequence (all scenarios)
  --setup-demo-policy  Lower policy thresholds for cleaner BLOCK demos
  --restore-policy     Restore production thresholds
  --check           Check prerequisites
  --show-blocked    Show current nftables block set
  -h, --help        Show this help

Environment variables:
  DNS_SERVER            DNS to target (auto: 127.0.0.53 for journald, 127.0.0.1 for file/udp)
  MINIFW_DNS_SOURCE     Override detected source (journald|file|udp|none)
  DEMO_VM_IP            Override detected VM IP (auto-read from /etc/ritapi/vsentinel.env)
  DJANGO_DASHBOARD_URL  Override dashboard base URL (default: http://<detected-ip>)
  MINIFW_EVENTS_URL     Override events URL (default: http://<detected-ip>/ops/minifw/events)

Examples:
  DNS_SERVER=10.0.0.1 ./demos/demo_traffic_gen.sh --scenario A
  DEMO_VM_IP=203.0.113.5 sudo ./demos/demo_traffic_gen.sh --scenario C
EOF
}

case "${1:-}" in
    --scenario)
        case "${2:-}" in
            A) scenario_a ;;
            B) scenario_b ;;
            C) scenario_c ;;
            D) scenario_d ;;
            *) echo "Unknown scenario: ${2:-}. Use A, B, C, or D."; exit 1 ;;
        esac
        ;;
    --all)             run_all ;;
    --setup-demo-policy) setup_demo_policy ;;
    --restore-policy)  restore_policy ;;
    --check)           check_prereqs ;;
    --show-blocked)    show_blocked_ips ;;
    -h|--help)         usage ;;
    "")
        usage
        echo ""
        info "Tip: Run --check first to verify prerequisites."
        ;;
    *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
esac
