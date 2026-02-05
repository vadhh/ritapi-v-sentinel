#!/usr/bin/env bash
set -e

# VSentinel Scope Gate
# Objective: Ensure the environment and codebase are safe for gambling-only deployment.

echo "[VSentinel] Initiating Scope Gate Scan..."

# 1. Environment Check
if [[ "${GAMBLING_ONLY}" != "1" ]]; then
    echo "[VSentinel] CRITICAL: GAMBLING_ONLY environment variable not set to '1'. Aborting."
    exit 1
fi

# 2. Prohibited Keyword Scan
# Keywords: malware, ransomware, ddos, rm -rf, bitcoin_miner
# We exclude the gate script itself and .git to avoid false positives on the list itself.

PROHIBITED_TERMS="malware|ransomware|ddos|rm -rf|bitcoin_miner"
EXCLUDE_PATTERN="vsentinel_scope_gate.sh|.git"

echo "[VSentinel] Scanning for prohibited terms: ${PROHIBITED_TERMS}"

if grep -rE "${PROHIBITED_TERMS}" . | grep -vE "${EXCLUDE_PATTERN}"; then
    echo "[VSentinel] CRITICAL: Prohibited logic detected in codebase!"
    exit 1
else
    echo "[VSentinel] Clean. No prohibited terms found."
fi

echo "[VSentinel] Scope Gate Passed."
exit 0
