#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo $0"; exit 1; fi

CONF="/etc/dnsmasq.conf"
LOG="/var/log/dnsmasq.log"

touch "${LOG}" || true
chmod 640 "${LOG}" || true

grep -q "^log-queries" "${CONF}" 2>/dev/null || echo "log-queries" >> "${CONF}"
grep -q "^log-facility=" "${CONF}" 2>/dev/null || echo "log-facility=${LOG}" >> "${CONF}"

echo "Enabled dnsmasq query logging to ${LOG}"
echo "Restart: sudo systemctl restart dnsmasq"
