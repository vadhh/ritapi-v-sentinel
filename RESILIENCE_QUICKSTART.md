# MiniFW Resilience Implementation - Quick Reference

## Problem Statement
MiniFW was experiencing restart storms when DNS telemetry (dnsmasq logs) was unavailable, violating the "fail-open telemetry, fail-closed security" principle.

## Root Causes
1. DNS iterator would `return` (exit) when log file missing → generator stopped
2. systemd had `Wants=dnsmasq.service` → hard dependency
3. No pluggable backend system → inflexible for different environments
4. Hard-threat gates tied to DNS events → no DNS = no enforcement

## Solution Summary

### 1. DNS Iterator Never Exits ✅
**Changed**: `collector_dnsmasq.py`
- `yield None, None` instead of `return` when file missing
- Infinite wait loops with periodic checks
- Handles file deletion, rotation, and recreation gracefully
- Both file and UDP backends stay alive forever

### 2. Removed dnsmasq Hard Requirement ✅
**Changed**: `systemd/minifw-ai.service` + `install.sh`
- Removed `Wants=dnsmasq.service`
- Added comment explaining optional nature
- Added `StartLimitBurst=5` to prevent restart storms

### 3. Pluggable DNS Backends ✅
**Changed**: `main.py`
- Environment: `MINIFW_DNS_SOURCE=file|journald|udp|none`
- Empty iterator when source unavailable
- Main loop skips empty events but keeps running

### 4. Hard-Threat Gates Always-On ✅
**Changed**: `main.py`
- `pump_flows()` runs every iteration (not just on DNS events)
- Flow tracking, PPS limits, burst detection ALWAYS active
- AI modules are optional amplifiers

### 5. Installer Pre-Flight + Status File ✅
**Changed**: `install.sh`
- DNS detection before deployment
- Yellow warning when no telemetry
- Writes `/var/log/ritapi/deployment_state.json`
- Never aborts on missing DNS

### 6. Self-Test Degraded Mode Support ✅
**Changed**: `scripts/vsentinel_selftest.sh`
- Reports "RUNNING (DEGRADED)" vs "RUNNING (FULL)"
- Degraded mode is NOT a failure
- Includes deployment state in proof pack

## Key Files Modified

| File | Changes |
|------|---------|
| `app/minifw_ai/collector_dnsmasq.py` | Never-exiting iterators |
| `app/minifw_ai/main.py` | Pluggable backends + empty event handling |
| `systemd/minifw-ai.service` | No dnsmasq dependency + restart limits |
| `install.sh` | DNS detection + deployment state writer |
| `scripts/vsentinel_selftest.sh` | Degraded mode checks |

## Environment Variables

```bash
# /etc/ritapi/vsentinel.env (auto-configured by installer)
MINIFW_DNS_SOURCE=none          # file|journald|udp|none
DEGRADED_MODE=1                 # 0=full, 1=degraded
MINIFW_DNS_LOG_PATH=            # Path when source=file
MINIFW_DNS_UDP_PORT=5514        # Port when source=udp
```

## Operational Modes

### FULL MODE (DNS Available)
```
✓ DNS domain analysis
✓ Flow tracking
✓ Hard-threat gates
✓ AI/ML scoring
✓ Complete visibility
```

### DEGRADED MODE (No DNS)
```
⚠ DNS analysis: LIMITED
✓ Flow tracking: ACTIVE
✓ Hard-threat gates: ACTIVE  
✓ IP blocking: ACTIVE
✓ PPS/burst limits: ACTIVE
```

## Testing

### Check Current Mode
```bash
# Method 1: Deployment state
cat /var/log/ritapi/deployment_state.json | jq '.dns_telemetry.status'

# Method 2: Service logs
journalctl -u minifw-ai -n 50 | grep -i degraded

# Method 3: Self-test
/opt/ritapi-v-sentinel/scripts/vsentinel_selftest.sh
```

### Verify No Restart Storm
```bash
# Should show stable uptime, no flapping
systemctl status minifw-ai

# Should show no recent restarts
journalctl -u minifw-ai --since "1 hour ago" | grep -i "started\|stopped"
```

### Simulate DNS Failure
```bash
# Stop dnsmasq (if running)
systemctl stop dnsmasq

# MiniFW should continue running
systemctl status minifw-ai
# Active: active (running)

# Logs show graceful degradation
journalctl -u minifw-ai -f
# [DEGRADED_MODE] DNS telemetry disabled
# [DEGRADED_MODE] Running with flow tracking and hard-threat gates only
```

## Deployment Checklist

Before deploying:
- [ ] Review `/var/log/ritapi/deployment_state.json` after install
- [ ] Verify service stays up without DNS: `systemctl status minifw-ai`
- [ ] Run self-test: `scripts/vsentinel_selftest.sh`
- [ ] Check no restart loops: `journalctl -u minifw-ai --since "10 minutes ago"`

After deployment:
- [ ] Monitor for warning in logs: `grep -i "degraded" /var/log/syslog`
- [ ] Confirm security gates active: Check ipset blocks `ipset list minifw_block_v4`
- [ ] Test enforcement: Trigger burst condition, verify blocking

## Architecture Principles

1. **Fail-Open Telemetry**: DNS absence doesn't stop service
2. **Fail-Closed Security**: Enforcement continues without DNS
3. **Graceful Degradation**: Service always provides value
4. **Never Exit**: Iterators run forever, waiting for data
5. **Explicit Warnings**: Operators know deployment state

## Quick Fixes

### Service not starting
```bash
# Check environment config
cat /etc/ritapi/vsentinel.env

# Try manual start to see errors
/opt/minifw_ai/venv/bin/python -m minifw_ai
```

### Still getting restarts
```bash
# Check systemd limits
systemctl show minifw-ai | grep -i limit

# Should show:
# StartLimitBurst=5
# StartLimitIntervalUSec=5min
```

### Want to force degraded mode
```bash
# Edit config
echo "MINIFW_DNS_SOURCE=none" >> /etc/ritapi/vsentinel.env
echo "DEGRADED_MODE=1" >> /etc/ritapi/vsentinel.env

# Restart
systemctl restart minifw-ai
```

## Success Criteria

✅ Service runs indefinitely without DNS  
✅ No restart storms in systemd  
✅ Hard-threat gates active in degraded mode  
✅ Self-test passes in both modes  
✅ Deployment state file created  
✅ Explicit warnings during install  

## Documentation

- Full details: `docs/DEGRADED_MODE_IMPLEMENTATION.md`
- Service file: `systemd/minifw-ai.service`
- Collector code: `app/minifw_ai/collector_dnsmasq.py`
- Main engine: `app/minifw_ai/main.py`

---

**Status**: ✅ All 6 requirements implemented  
**Philosophy**: Fail-Open Telemetry, Fail-Closed Security  
**Result**: Service runs forever, security never fully disabled
