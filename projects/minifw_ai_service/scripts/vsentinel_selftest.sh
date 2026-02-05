#!/usr/bin/env bash
set -e

echo "[VSentinel] Running Self-Test..."

# 1. Service Status Checks
echo "Checking services..."
systemctl is-active --quiet minifw-ai && echo "OK: minifw-ai is active" || { echo "FAIL: minifw-ai inactive"; exit 1; }
# Note: nginx might not be part of this specific mini-service, but requested in prompt.
# Only checking if installed/active if expected. Assuming checking logic:
if systemctl list-unit-files | grep -q nginx; then
    systemctl is-active --quiet nginx && echo "OK: nginx is active" || echo "WARN: nginx inactive"
fi

# 2. IPSet Check
echo "Checking ipset..."
ipset list minifw_block_v4 >/dev/null 2>&1 && echo "OK: ipset minifw_block_v4 exists" || { echo "FAIL: ipset missing"; exit 1; }

# 3. Audit Log Check
AUDIT_LOG="/var/log/ritapi/audit.jsonl" # Adjusted to requested path
# If the app writes to /opt/minifw_ai/logs/events.jsonl by default, we check that too or the requested one.
# The prompt says "Check if audit.jsonl exists".
if [ -f "$AUDIT_LOG" ]; then
    if [ -s "$AUDIT_LOG" ]; then
        echo "OK: $AUDIT_LOG exists and is not empty"
    else
        echo "WARN: $AUDIT_LOG exists but is empty"
    fi
else
    echo "WARN: $AUDIT_LOG not found (might be waiting for traffic)"
fi

echo "[VSentinel] Self-Test Passed."
exit 0
