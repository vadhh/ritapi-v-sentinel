#!/usr/bin/env bash
set -euo pipefail

# MiniFW-AI Testbed Initialization
# Usage: ./scripts/init_testbed.sh

TEST_ROOT="/tmp/minifw_testbed"
CONFIG_DIR="${TEST_ROOT}/config"
LOG_DIR="${TEST_ROOT}/logs"
SECRETS_DIR="${TEST_ROOT}/secrets"

echo "🚧 Initializing Testbed at ${TEST_ROOT}..."

# 1. Clean previous run
if [[ -d "${TEST_ROOT}" ]]; then
    echo "   Removing old testbed..."
    rm -rf "${TEST_ROOT}"
fi

# 2. Create Structure
mkdir -p "${CONFIG_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${SECRETS_DIR}"

# 3. Mock Sector Lock (Read-Only simulation target)
echo '{"sector": "education", "locked_at": "2024-01-01T00:00:00"}' > "${SECRETS_DIR}/sector.lock"
chmod 444 "${SECRETS_DIR}/sector.lock" # Read-only

# 4. Mock Policy (Read-Write)
cp config/policy.json "${CONFIG_DIR}/policy.json"

# 5. Generate Environment File
cat > "${TEST_ROOT}/.env" <<EOF
MINIFW_SECRET_KEY=test_secret_key_12345
MINIFW_ADMIN_PASSWORD=test_admin_pass
MINIFW_POLICY=${CONFIG_DIR}/policy.json
MINIFW_SECTOR_LOCK=${SECRETS_DIR}/sector.lock
EOF

# 6. Docker Compose Override (for testing)
cat > "${TEST_ROOT}/docker-compose.test.yml" <<EOF
version: '3.8'
services:
  minifw-test:
    build: .
    env_file: ${TEST_ROOT}/.env
    volumes:
      - ${CONFIG_DIR}:/app/config
      - ${SECRETS_DIR}:/etc/minifw:ro
      - ${LOG_DIR}:/var/log
    network_mode: "host"
    command: python3 -m pytest testing/
EOF

echo "✅ Testbed initialized."
echo "   Run tests: docker-compose -f ${TEST_ROOT}/docker-compose.test.yml up --build --abort-on-container-exit"
