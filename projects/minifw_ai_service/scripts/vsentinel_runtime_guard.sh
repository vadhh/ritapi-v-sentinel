#!/usr/bin/env bash
set -e

# VSentinel Runtime Guard
# Executed by Systemd ExecStartPre

CONFIG_FILE="/etc/ritapi/vsentinel.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "VSentinel: Config file missing ($CONFIG_FILE). Refusing to start."
    exit 1
fi

source "$CONFIG_FILE"

if [[ "$GAMBLING_ONLY" != "1" ]]; then
    echo "VSentinel: Runtime violation. GAMBLING_ONLY is not 1."
    exit 1
fi

echo "VSentinel: Runtime Environment Validated. Starting Service."
exit 0
