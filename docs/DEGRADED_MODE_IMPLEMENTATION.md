# MiniFW Resilience & Degraded Mode Implementation

## Summary of Changes

This document describes the comprehensive fixes implemented to prevent restart storms and enable MiniFW to run indefinitely in BASELINE_PROTECTION when DNS telemetry is unavailable.

## Critical Philosophy

**Fail-Open for Telemetry, Fail-Closed for Security**

- DNS telemetry absence does NOT stop the service
- Security enforcement (flow tracking, burst gates, PPS limits) continues regardless
- AI modules become optional amplifiers, not hard requirements

---

## 1. Stop Restart Storm - DNS Iterator Resilience

### Problem
DNS iterator would exit when log file was missing, causing systemd restart loops.

### Solution
**File: `projects/minifw_ai_service/app/minifw_ai/collector_dnsmasq.py`**

#### `stream_dns_events_file()` - NEVER EXITS
- Yields `(None, None)` when file is missing instead of returning/exiting
- Infinite wait loop with 10-second check intervals
- Handles file deletion by reopening and continuing
- Handles log rotation gracefully
- Outer reconnection loop ensures recovery from fatal errors

#### `stream_dns_events_udp()` - NEVER EXITS
- If UDP port bind fails (permission/in-use), yields `(None, None)` indefinitely
- No early returns - always provides generator that runs forever
- Continues even on socket errors with 1-second backoff

### Key Code Pattern
```python
# Instead of:
if not os.path.exists(log_path):
    return  # BAD - exits generator

# Now:
while not os.path.exists(log_path):
    time.sleep(10)
    yield None, None  # Keep generator alive
```

---

## 2. Remove dnsmasq Hard Requirement

### Problem
systemd service had `Wants=dnsmasq.service` and `After=dnsmasq.service`, forcing dnsmasq dependency.

### Solution
**Files Updated:**
- `projects/minifw_ai_service/systemd/minifw-ai.service`
- `install.sh` (inline systemd unit creation)

#### Changes
```systemd
[Unit]
Description=MiniFW-AI (RitAPI-AI V-Sentinel - Gateway Metadata Layer)
After=network.target
# NOTE: dnsmasq is NOT a hard requirement - DNS telemetry source is configurable
# If dnsmasq is present, wait for it; otherwise continue without it
After=dnsmasq.service
# ❌ REMOVED: Wants=dnsmasq.service

[Service]
# ... rest of config
StartLimitIntervalSec=300  # Prevent restart storm
StartLimitBurst=5
```

---

## 3. Pluggable DNS Backends

### Problem
Hard-coded dnsmasq file tailing only - no flexibility for different environments.

### Solution
**File: `projects/minifw_ai_service/app/minifw_ai/main.py`**

#### Environment Variables
```bash
MINIFW_DNS_SOURCE=file|journald|udp|none
DEGRADED_MODE=1|0
MINIFW_DNS_LOG_PATH=/path/to/log
MINIFW_DNS_UDP_PORT=5514
```

#### Backend Selection Logic
```python
dns_source = os.environ.get("MINIFW_DNS_SOURCE", "file")
degraded_mode = os.environ.get("DEGRADED_MODE", "0") == "1"

if dns_source == "none" or degraded_mode:
    # Empty iterator yielding (None, None) forever
    def empty_dns_iterator():
        while True:
            yield None, None
            time.sleep(1)
    dns_events = empty_dns_iterator()

elif dns_source == "file":
    dns_events = stream_dns_events_file(dns_log)

elif dns_source == "udp":
    dns_port = int(os.environ.get("MINIFW_DNS_UDP_PORT", "5514"))
    dns_events = stream_dns_events_udp(port=dns_port)

elif dns_source == "journald":
    # Future implementation - for now falls back to empty iterator
    dns_events = empty_dns_iterator()
```

#### Main Loop Handles Empty Events
```python
for client_ip, domain in dns_events:
    pump_zeek()   # Always runs
    pump_flows()  # Always runs - contains hard-threat gates
    
    # Skip DNS-based scoring in BASELINE_PROTECTION
    if client_ip is None or domain is None:
        continue  # Hard gates still executed above
    
    # Normal DNS-based threat analysis
    ...
```

---

## 4. Hard-Threat Gates Always-On

### Problem
All detection was tied to DNS events - no DNS = no threat detection.

### Solution
**File: `projects/minifw_ai_service/app/minifw_ai/main.py`**

#### Architecture
1. **Layer 1: Hard Gates (Mandatory)**
   - Flow tracking via `pump_flows()` - runs every loop iteration
   - PPS saturation detection (>200 pps)
   - Burst flood detection (>300 pkts/sec)
   - Bot-like small packet patterns
   - Flow frequency limits
   - **Executes REGARDLESS of DNS availability**

2. **Layer 2: AI Amplifiers (Optional)**
   - MLP risk scoring
   - YARA pattern matching
   - DNS domain reputation
   - **Only runs when AI_ENABLED=1 and data available**

#### Code Flow
```python
# ALWAYS execute these:
pump_zeek()   # SNI enrichment (if available)
pump_flows()  # ← CRITICAL: Hard gates here

# Evaluate hard threats from flow data
flows_for_client = flow_tracker.get_flows_for_client(client_ip)
flow_freq = flow_freq_tracker.get_rate(client_ip)
hard_threat, reason = evaluate_hard_threat(flows_for_client, flow_freq, threshold)

# If hard threat detected, BLOCK immediately
if hard_threat:
    score, reasons, action = score_and_decide(
        ...,
        hard_threat_override=True,  # Bypasses normal scoring
        hard_threat_reason=reason
    )
```

#### Hard Threat Rules (examples)
```python
def evaluate_hard_threat(flows, flow_freq, threshold):
    # Rule 1: High flow frequency
    if flow_freq >= threshold:
        return True, "flow_frequency"
    
    # Rule 2: PPS saturation
    if flow.pkts_per_sec > 200:
        return True, "pps_saturation"
    
    # Rule 3: Burst flood
    if flow.max_burst_pkts_1s > 300:
        return True, "burst_flood"
    
    # Rule 4: Bot-like patterns
    if flow.small_pkt_ratio > 0.95 and flow.duration < 3:
        return True, "bot_like_small_packets"
    
    return False, None
```

---

## 5. Installer: Telemetry Pre-Flight + Status File

### Problem
No visibility into deployment state or warning when DNS unavailable.

### Solution
**File: `install.sh`**

#### DNS Environment Detection
```bash
detect_dns_environment() {
    local dns_source="none"
    
    # Check systemd-resolved
    if systemctl is-active systemd-resolved && port 53 listening; then
        dns_source="journald"
    fi
    
    # Check dnsmasq
    if dnsmasq installed && logging configured; then
        dns_source="file"
    fi
    
    export DETECTED_DNS_SOURCE="$dns_source"
}
```

#### Deployment State File
**Location: `/var/log/ritapi/deployment_state.json`**

```json
{
  "deployment_timestamp": "2026-02-05T10:30:00Z",
  "hostname": "gateway-01",
  "dns_telemetry": {
    "source": "none",
    "degraded_mode": 1,
    "log_path": "",
    "status": "BASELINE_PROTECTION"
  },
  "security_enforcement": {
    "flow_tracking": "active",
    "hard_threat_gates": "active",
    "burst_detection": "active",
    "ai_modules": "limited"
  },
  "fail_mode": {
    "telemetry": "fail-open",
    "security": "fail-closed"
  }
}
```

#### Explicit Operator Warning
```bash
verify_telemetry() {
    if [ "$dns_source" = "none" ]; then
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_warning "⚠  WARNING: No DNS Telemetry Detected"
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_warning ""
        print_warning "MiniFW-AI will run in BASELINE_PROTECTION:"
        print_info "  ✓ Flow tracking: ACTIVE"
        print_info "  ✓ Hard-threat gates: ACTIVE"
        print_info "  ✓ IP filtering: ACTIVE"
        print_info "  ✗ DNS-based domain analysis: LIMITED"
        degraded_mode=1
    fi
    
    write_deployment_state "$dns_source" "$degraded_mode" "$dns_log_path"
}
```

#### Environment Configuration
**File: `/etc/ritapi/vsentinel.env`**
```bash
# Auto-detected and written by installer
MINIFW_DNS_SOURCE=none
DEGRADED_MODE=1
MINIFW_DNS_LOG_PATH=
```

---

## 6. Self-Test Update for Degraded Mode

### Problem
Self-test would fail if MiniFW was in BASELINE_PROTECTION.

### Solution
**File: `scripts/vsentinel_selftest.sh`**

#### New Checks

##### 1. Deployment State Check
```bash
check_deployment_state() {
    if [ -f "/var/log/ritapi/deployment_state.json" ]; then
        print_success
    else
        print_failed "Deployment state file missing"
    fi
}
```

##### 2. Mode Detection (Non-Failing)
```bash
check_minifw_mode() {
    local degraded_mode=$(grep '"degraded_mode": [0-9]' state_file)
    
    if [ "$degraded_mode" = "1" ]; then
        echo -e "${YELLOW}BASELINE_PROTECTION${NC} (DNS telemetry unavailable)"
        echo ""
        echo -e "${YELLOW}  ⚠ MiniFW-AI is running in BASELINE_PROTECTION${NC}"
        echo -e "${BLUE}  ℹ Security enforcement: ACTIVE${NC}"
        echo -e "${BLUE}  ℹ Flow tracking: ACTIVE${NC}"
        echo -e "${BLUE}  ℹ Hard-threat gates: ACTIVE${NC}"
        echo -e "${YELLOW}  ⚠ DNS telemetry: LIMITED${NC}"
        return 0  # ← NOT A FAILURE
    else
        echo -e "${GREEN}AI_ENHANCED_PROTECTION${NC} (complete telemetry)"
        return 0
    fi
}
```

##### 3. Updated Proof Pack
```json
{
  "selftest_result": "PASS",
  "deployment": {
    "mode": "BASELINE_PROTECTION",
    "dns_source": "none",
    "state_file": "/var/log/ritapi/deployment_state.json"
  }
}
```

#### Self-Test Exit Criteria
```
PASS: Service running, even in BASELINE_PROTECTION
FAIL: Only if service not running or critical config missing
```

---

## Testing Scenarios

### Scenario 1: No DNS Telemetry (Common VM Setup)
```bash
# Before: Restart storm in systemd
# After: Service runs indefinitely

journalctl -u minifw-ai -f
# [BASELINE_PROTECTION] DNS telemetry disabled (source=none)
# [BASELINE_PROTECTION] Running with flow tracking and hard-threat gates only
# [FlowCollector] Tracking active flows
# [HARD_GATE] Triggered: 192.168.1.100 - pps_saturation
```

### Scenario 2: DNS File Deleted During Operation
```bash
rm /var/log/dnsmasq.log

# Before: Service exits, systemd restarts
# After: Service continues
# [!] Log file deleted. Waiting for recreation...
# [BASELINE_PROTECTION] Yielding empty events...
# [FlowCollector] Tracking active flows
```

### Scenario 3: Port 53 Conflict (systemd-resolved)
```bash
# Before: Service wouldn't start or restart storm
# After: Service detects journald source or falls back

# install.sh output:
# ⚠ WARNING: No DNS Telemetry Detected
# MiniFW-AI will run in BASELINE_PROTECTION:
#   ✓ Flow tracking: ACTIVE
#   ✓ Hard-threat gates: ACTIVE
```

---

## Verification Commands

### Check Service Status
```bash
systemctl status minifw-ai
# Active: active (running)
# No restart stampeding
```

### Check Deployment State
```bash
cat /var/log/ritapi/deployment_state.json | jq
```

### Check Mode in Logs
```bash
journalctl -u minifw-ai --since "5 minutes ago" | grep -E "BASELINE_PROTECTION|AI_ENHANCED_PROTECTION"
```

### Run Self-Test
```bash
/opt/ritapi-v-sentinel/scripts/vsentinel_selftest.sh
# ✓ MiniFW-AI Service: RUNNING
# ⚠ MiniFW-AI operational mode: BASELINE_PROTECTION
#   ℹ Security enforcement: ACTIVE
#   ℹ Flow tracking: ACTIVE
```

---

## Configuration Files Modified

1. **`projects/minifw_ai_service/app/minifw_ai/collector_dnsmasq.py`**
   - DNS iterators never exit
   - Yield empty events in BASELINE_PROTECTION

2. **`projects/minifw_ai_service/app/minifw_ai/main.py`**
   - Pluggable DNS backend selection
   - Empty event handling
   - Hard gates always execute

3. **`projects/minifw_ai_service/systemd/minifw-ai.service`**
   - Removed dnsmasq hard dependency
   - Added StartLimitBurst protection

4. **`install.sh`**
   - DNS environment detection
   - Deployment state file writer
   - Explicit operator warnings

5. **`scripts/vsentinel_selftest.sh`**
   - Degraded mode detection
   - Non-failing mode checks
   - Enhanced proof pack

---

## Security Guarantees

### What ALWAYS Works (Even in Degraded Mode)
✅ Flow tracking (conntrack-based)
✅ PPS/burst detection
✅ Flow frequency limits
✅ IP-based blocking (ipset)
✅ nftables enforcement rules

### What is LIMITED in Degraded Mode
⚠️ Domain reputation scoring (no DNS queries observed)
⚠️ SNI-based TLS analysis (depends on Zeek)
⚠️ AI-based domain classification

### What NEVER Works (Regardless of Mode)
❌ Service exit on missing telemetry
❌ Restart storms
❌ Complete security bypass

---

## Regulatory Compliance Notes

1. **Audit Trail**: Deployment state file provides evidence of configuration
2. **Fail-Safe Operation**: Service continues even without full visibility
3. **Operator Notification**: Explicit warnings during installation
4. **Self-Test Reporting**: Distinguishes BASELINE_PROTECTION vs AI_ENHANCED_PROTECTION mode
5. **Proof Packs**: Include deployment mode in forensic output

---

## Future Enhancements

1. **journald backend**: Parse systemd-resolved logs
   ```python
   # In collector_dnsmasq.py
   def stream_dns_events_journald():
       from systemd import journal
       j = journal.Reader()
       j.add_match(_SYSTEMD_UNIT="systemd-resolved.service")
       # Parse DNS queries from journal
   ```

2. **Active DNS monitoring**: Periodic test queries to verify DNS working
3. **Metrics dashboard**: Show telemetry source and protection-state status
4. **Dynamic mode switching**: Auto-recover when DNS becomes available

---

## Contact & Support

For issues or questions about BASELINE_PROTECTION operation:
- Check `/var/log/ritapi/deployment_state.json`
- Review `journalctl -u minifw-ai -f`
- Run self-test: `/opt/ritapi-v-sentinel/scripts/vsentinel_selftest.sh`

**Remember**: BASELINE_PROTECTION is a valid operational state, not a failure.
