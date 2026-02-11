#!/usr/bin/env bash
################################################################################
# V-Sentinel Self-Test Script - Post-Installation Verification
#
# This script performs comprehensive post-installation verification and
# generates a proof pack for regulatory auditing.
#
# Exit Codes:
#   0 = All critical checks passed
#   1 = One or more critical checks failed
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="/etc/ritapi/vsentinel.env"
PROOF_PACK_DIR="/var/log/ritapi/proof_packs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOSTNAME=$(hostname)
SELFTEST_RESULT="PASS"
FAILED_CHECKS=()

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  V-Sentinel Post-Installation Self-Test${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

print_check() {
    echo -ne "${BLUE}▶${NC} $1 ... "
}

print_success() {
    echo -e "${GREEN}✓${NC}"
}

print_failed() {
    echo -e "${RED}✗${NC}"
    FAILED_CHECKS+=("$1")
    SELFTEST_RESULT="FAIL"
}

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_result() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    if [ "$SELFTEST_RESULT" = "PASS" ]; then
        echo -e "${GREEN}  Self-Test Result: PASS ✓${NC}"
    else
        echo -e "${RED}  Self-Test Result: FAIL ✗${NC}"
    fi
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
}

################################################################################
# Service Validation Checks
################################################################################

check_service_status() {
    local service_name=$1
    local service_display=$2
    
    print_check "Service running: $service_display"
    
    if systemctl is-active --quiet "$service_name" 2>/dev/null; then
        print_success
        return 0
    else
        print_failed "Service not running: $service_display"
        return 1
    fi
}

check_service_enabled() {
    local service_name=$1
    local service_display=$2
    
    print_check "Service enabled: $service_display"
    
    if systemctl is-enabled --quiet "$service_name" 2>/dev/null; then
        print_success
        return 0
    else
        print_failed "Service not enabled: $service_display"
        return 1
    fi
}

################################################################################
# System Configuration Checks
################################################################################

check_deployment_state() {
    local state_file="/var/log/ritapi/deployment_state.json"
    
    print_check "Deployment state file exists"
    
    if [ -f "$state_file" ]; then
        print_success
        return 0
    else
        print_failed "Deployment state file missing: $state_file"
        return 1
    fi
}

check_minifw_mode() {
    local state_file="/var/log/ritapi/deployment_state.json"
    
    print_check "MiniFW-AI operational mode"
    
    if [ ! -f "$state_file" ]; then
        echo -e "${YELLOW}UNKNOWN${NC} (state file not found)"
        return 0  # Non-critical
    fi
    
    local degraded_mode=$(grep -oP '(?<="degraded_mode": )[^,}]*' "$state_file" 2>/dev/null || echo "unknown")
    
    if [ "$degraded_mode" = "1" ] || [ "$degraded_mode" = "true" ]; then
        echo -e "${YELLOW}BASELINE_PROTECTION${NC} (DNS telemetry unavailable)"
        echo ""
        echo -e "${YELLOW}  ⚠ MiniFW-AI is running in BASELINE_PROTECTION${NC}"
        echo -e "${BLUE}  ℹ Security enforcement: ACTIVE${NC}"
        echo -e "${BLUE}  ℹ Flow tracking: ACTIVE${NC}"
        echo -e "${BLUE}  ℹ Hard-threat gates: ACTIVE${NC}"
        echo -e "${YELLOW}  ⚠ DNS telemetry: LIMITED${NC}"
        return 0  # Not a failure - degraded mode is valid
    elif [ "$degraded_mode" = "0" ] || [ "$degraded_mode" = "false" ]; then
        echo -e "${GREEN}AI_ENHANCED_PROTECTION${NC} (complete telemetry)"
        return 0
    else
        echo -e "${YELLOW}UNKNOWN${NC} (degraded_mode=$degraded_mode)"
        return 0  # Non-critical
    fi
}

check_ipset_exists() {
    print_check "IPset exists: minifw_block_v4"
    
    if ipset list minifw_block_v4 >/dev/null 2>&1; then
        print_success
        return 0
    else
        print_failed "IPset not found: minifw_block_v4"
        return 1
    fi
}

check_config_file_exists() {
    print_check "Configuration file exists"
    
    if [ -f "$CONFIG_FILE" ]; then
        print_success
        return 0
    else
        print_failed "Configuration file missing: $CONFIG_FILE"
        return 1
    fi
}

check_gambling_only_config() {
    print_check "GAMBLING_ONLY configuration"
    
    local gambling_only
    gambling_only=$(grep -oP '(?<=GAMBLING_ONLY=)[^$\n]*' "$CONFIG_FILE" 2>/dev/null || echo "")
    
    if [ "$gambling_only" = "1" ]; then
        print_success
        return 0
    else
        print_failed "GAMBLING_ONLY not set to 1 (found: $gambling_only)"
        return 1
    fi
}

################################################################################
# Proof Pack Generation
################################################################################

create_proof_pack_directory() {
    if [ ! -d "$PROOF_PACK_DIR" ]; then
        mkdir -p "$PROOF_PACK_DIR"
        chmod 750 "$PROOF_PACK_DIR"
    fi
}

generate_proof_pack() {
    local proof_file="$PROOF_PACK_DIR/selftest_${TIMESTAMP//[:]/}.json"
    
    # Collect service statuses
    local ritapi_gunicorn_active="false"
    local minifw_ai_active="false"
    local nginx_active="false"
    
    systemctl is-active --quiet ritapi-gunicorn && ritapi_gunicorn_active="true" || true
    systemctl is-active --quiet minifw-ai && minifw_ai_active="true" || true
    systemctl is-active --quiet nginx && nginx_active="true" || true
    
    # Collect gambling_only value
    local gambling_only
    gambling_only=$(grep -oP '(?<=GAMBLING_ONLY=)[^$\n]*' "$CONFIG_FILE" 2>/dev/null || echo "unknown")
    
    # Collect deployment state
    local state_file="/var/log/ritapi/deployment_state.json"
    local deployment_mode="unknown"
    local dns_source="unknown"
    if [ -f "$state_file" ]; then
        deployment_mode=$(grep -oP '(?<="status": ")[^"]*' "$state_file" 2>/dev/null || echo "unknown")
        dns_source=$(grep -oP '(?<="source": ")[^"]*' "$state_file" 2>/dev/null || echo "unknown")
    fi
    
    # Generate JSON proof pack
    cat > "$proof_file" <<EOF
{
  "selftest_timestamp": "$TIMESTAMP",
  "hostname": "$HOSTNAME",
  "kernel_version": "$(uname -r)",
  "selftest_result": "$SELFTEST_RESULT",
  "services": {
    "ritapi-gunicorn": {
      "active": $ritapi_gunicorn_active,
      "enabled": $(systemctl is-enabled --quiet ritapi-gunicorn 2>/dev/null && echo "true" || echo "false")
    },
    "minifw-ai": {
      "active": $minifw_ai_active,
      "enabled": $(systemctl is-enabled --quiet minifw-ai 2>/dev/null && echo "true" || echo "false")
    },
    "nginx": {
      "active": $nginx_active,
      "enabled": $(systemctl is-enabled --quiet nginx 2>/dev/null && echo "true" || echo "false")
    }
  },
  "configuration": {
    "gambling_only": "$gambling_only",
    "config_file": "$CONFIG_FILE",
    "config_readable": $([ -r "$CONFIG_FILE" ] && echo "true" || echo "false")
  },
  "deployment": {
    "mode": "$deployment_mode",
    "dns_source": "$dns_source",
    "state_file": "$state_file"
  },
  "ipset": {
    "minifw_block_v4_exists": $(ipset list minifw_block_v4 >/dev/null 2>&1 && echo "true" || echo "false")
  },
  "failed_checks": [
$(for check in "${FAILED_CHECKS[@]}"; do
    echo "    \"$check\","
done | sed '$ s/,$//')
  ]
}
EOF
    
    chmod 640 "$proof_file"
    echo "$proof_file"
}

################################################################################
# Main Self-Test Flow
################################################################################

main() {
    print_header
    
    print_section "Service Status Checks"
    check_service_status "ritapi-gunicorn" "RitAPI Gunicorn (Django)" || true
    check_service_status "minifw-ai" "MiniFW-AI Service" || true
    check_service_status "nginx" "Nginx Web Server" || true
    
    print_section "Service Enablement Checks"
    check_service_enabled "ritapi-gunicorn" "RitAPI Gunicorn" || true
    check_service_enabled "minifw-ai" "MiniFW-AI Service" || true
    check_service_enabled "nginx" "Nginx Web Server" || true
    
    print_section "System Configuration Checks"
    check_config_file_exists || true
    check_gambling_only_config || true
    check_deployment_state || true
    check_minifw_mode || true
    check_ipset_exists || true
    
    print_section "Proof Pack Generation"
    print_check "Creating proof pack"
    create_proof_pack_directory
    PROOF_FILE=$(generate_proof_pack)
    if [ -f "$PROOF_FILE" ]; then
        print_success
        echo ""
        echo -e "${BLUE}Proof pack generated:${NC}"
        echo "  $PROOF_FILE"
    else
        print_failed "Failed to generate proof pack"
    fi
    
    print_result
    
    # Print summary of failed checks
    if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}Failed Checks:${NC}"
        for check in "${FAILED_CHECKS[@]}"; do
            echo -e "  ${RED}✗${NC} $check"
        done
    fi
    
    echo ""
    
    # Exit with appropriate code
    if [ "$SELFTEST_RESULT" = "PASS" ]; then
        echo -e "${GREEN}✓ All critical checks passed - Installation verified${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some checks failed - Please review the output above${NC}"
        exit 1
    fi
}

# Run main self-test
main
