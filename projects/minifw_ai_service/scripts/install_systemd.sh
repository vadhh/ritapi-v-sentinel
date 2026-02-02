#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo $0"; exit 1; fi

APP_ROOT="/opt/minifw_ai"
UNIT_DST="/etc/systemd/system/minifw-ai.service"
ENV_DIR="/etc/minifw"
ENV_FILE="${ENV_DIR}/minifw.env"

# 1. Create Environment File
mkdir -p "${ENV_DIR}"
chmod 755 "${ENV_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Creating secure environment file: ${ENV_FILE}"
    
    # Generate random secret key (32 bytes hex)
    SECRET_KEY=$(openssl rand -hex 32)
    # Generate random admin password if not provided
    ADMIN_PASS=$(openssl rand -base64 12)
    
    cat > "${ENV_FILE}" <<EOF
MINIFW_SECRET_KEY=${SECRET_KEY}
MINIFW_ADMIN_PASSWORD=${ADMIN_PASS}
EOF
    chmod 600 "${ENV_FILE}"
    echo "✅ Generated new secrets."
    echo "⚠️  Admin Password: ${ADMIN_PASS}"
    echo "⚠️  Save this password! It is stored in ${ENV_FILE}"
else
    echo "✅ Environment file exists: ${ENV_FILE}"
fi

# 2. Update Systemd Unit to use EnvironmentFile
# We assume the source unit file doesn't have it, so we inject it or use a sed replacement if we copied it.
# Better: Write the unit file content directly here or modify the copied one.
cp -f ./systemd/minifw-ai.service "${UNIT_DST}"

# Inject EnvironmentFile directive into the [Service] section
if ! grep -q "EnvironmentFile=" "${UNIT_DST}"; then
    sed -i '/^\[Service\]/a EnvironmentFile=/etc/minifw/minifw.env' "${UNIT_DST}"
fi

cat > "${APP_ROOT}/run_minifw.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=/opt/minifw_ai/app
exec /opt/minifw_ai/venv/bin/python -m minifw_ai
EOF
chmod +x "${APP_ROOT}/run_minifw.sh"

systemctl daemon-reload
systemctl enable --now minifw-ai

echo "Service installed & started: minifw-ai"
echo "Check: systemctl status minifw-ai --no-pager"
