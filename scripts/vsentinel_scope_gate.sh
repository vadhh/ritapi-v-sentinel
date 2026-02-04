#!/usr/bin/env bash
################################################################################
# V-Sentinel Scope Gate Script - Install-Time Validation
#
# This script performs fail-closed validation at installation time to ensure
# the system is configured as gambling-only before services can start.
#
# Exit Codes:
#   0 = All checks passed, safe to proceed
#   1 = Validation failed, installation must stop
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="/etc/ritapi/vsentinel.env"
VALIDATION_FAILED=0

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  V-Sentinel Scope Gate Validation${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
}

print_check() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_fatal() {
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}FATAL VALIDATION ERROR${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}$1${NC}"
    echo ""
    echo "Installation cannot proceed. Please fix the configuration and try again."
}

################################################################################
# Validation Checks
################################################################################

check_config_file_exists() {
    print_check "Checking if V-Sentinel configuration exists..."
    
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Configuration file not found: $CONFIG_FILE"
        print_fatal "V-Sentinel environment configuration is missing.\n\nExpected location: $CONFIG_FILE\nPlease ensure vsentinel.env was created in /etc/ritapi/"
        VALIDATION_FAILED=1
        return 1
    fi
    
    print_success "Configuration file found: $CONFIG_FILE"
}

check_gambling_only_enabled() {
    print_check "Checking GAMBLING_ONLY setting..."
    
    local gambling_only
    gambling_only=$(grep -oP '(?<=GAMBLING_ONLY=)[^$\n]*' "$CONFIG_FILE" || true)
    
    if [ -z "$gambling_only" ]; then
        print_error "GAMBLING_ONLY variable not found in configuration"
        print_fatal "The GAMBLING_ONLY setting is missing from $CONFIG_FILE\n\nThis is a critical regulatory requirement."
        VALIDATION_FAILED=1
        return 1
    fi
    
    if [ "$gambling_only" != "1" ]; then
        print_error "GAMBLING_ONLY is set to '$gambling_only' instead of '1'"
        print_fatal "V-Sentinel must be configured as gambling-only (GAMBLING_ONLY=1).\n\nCurrent setting: GAMBLING_ONLY=$gambling_only\n\nPlease update $CONFIG_FILE with the correct setting."
        VALIDATION_FAILED=1
        return 1
    fi
    
    print_success "GAMBLING_ONLY is correctly set to: 1"
}

check_allowed_detection_types() {
    print_check "Checking ALLOWED_DETECTION_TYPES setting..."
    
    local detection_types
    detection_types=$(grep -oP '(?<=ALLOWED_DETECTION_TYPES=)[^$\n]*' "$CONFIG_FILE" || true)
    
    if [ -z "$detection_types" ]; then
        print_error "ALLOWED_DETECTION_TYPES variable not found in configuration"
        print_fatal "The ALLOWED_DETECTION_TYPES setting is missing from $CONFIG_FILE\n\nThis is a critical regulatory requirement."
        VALIDATION_FAILED=1
        return 1
    fi
    
    if [ "$detection_types" != "gambling" ]; then
        print_error "ALLOWED_DETECTION_TYPES is set to '$detection_types' instead of 'gambling'"
        print_fatal "Only gambling-related detection is permitted (ALLOWED_DETECTION_TYPES=gambling).\n\nCurrent setting: ALLOWED_DETECTION_TYPES=$detection_types\n\nPlease update $CONFIG_FILE with the correct setting."
        VALIDATION_FAILED=1
        return 1
    fi
    
    print_success "ALLOWED_DETECTION_TYPES is correctly set to: gambling"
}

################################################################################
# Main Validation Flow
################################################################################

main() {
    print_header
    echo ""
    
    # Run all checks
    check_config_file_exists || true
    check_gambling_only_enabled || true
    check_allowed_detection_types || true
    
    echo ""
    
    if [ $VALIDATION_FAILED -eq 1 ]; then
        echo -e "${RED}════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}INSTALLATION HALTED: Validation Failed${NC}"
        echo -e "${RED}════════════════════════════════════════════════════════${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}All validation checks passed! ✓${NC}"
    echo -e "${GREEN}V-Sentinel is properly configured as gambling-only${NC}"
    echo -e "${GREEN}Installation may proceed${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    exit 0
}

# Run main validation
main
