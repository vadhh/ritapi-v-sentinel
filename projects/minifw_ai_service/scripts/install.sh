#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo $0"; exit 1; fi

APP_ROOT="/opt/minifw_ai"
apt-get update
apt-get install -y python3 python3-venv dnsmasq nftables ipset

mkdir -p "${APP_ROOT}/logs" "${APP_ROOT}/config/feeds" "${APP_ROOT}/app"

rm -rf "${APP_ROOT}/app/minifw_ai"
cp -r ./app/minifw_ai "${APP_ROOT}/app/"

cp -f ./config/policy.json "${APP_ROOT}/config/policy.json"
cp -f ./config/feeds/*.txt "${APP_ROOT}/config/feeds/" 2>/dev/null || true

python3 -m venv "${APP_ROOT}/venv"
"${APP_ROOT}/venv/bin/pip" install --upgrade pip
"${APP_ROOT}/venv/bin/pip" install -r ./requirements.txt

ipset create minifw_block_v4 hash:ip timeout 86400 -exist

echo "Installed MiniFW-AI to ${APP_ROOT}"
echo "Next: sudo ./scripts/enable_dnsmasq_logging.sh ; sudo ./scripts/install_systemd.sh"
