#!/usr/bin/env bash
################################################################################
# V-Sentinel Runtime Guard Script - Service Start Validation
#
# This script validates gambling-only configuration at service startup time.
# It is called by systemd as ExecStartPre to prevent service startup if
# validation fails.
#
# Exit Codes:
#   0 = All checks passed, service may start
#   1 = Validation failed, systemd will not start the service
################################################################################

set -euo pipefail

# Configuration
CONFIG_FILE="/etc/ritapi/vsentinel.env"
VALIDATION_FAILED=0

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo "[V-SENTINEL-GUARD] INFO: $1" >&2
}

log_error() {
    echo "[V-SENTINEL-GUARD] ERROR: $1" >&2
}

log_fatal() {
    echo "[V-SENTINEL-GUARD] FATAL: $1" >&2
}

################################################################################
# Validation Checks
################################################################################

check_config_file_exists() {
    log_info "Checking V-Sentinel configuration file..."
    
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_fatal "V-Sentinel environment configuration is missing. Service startup blocked."
        VALIDATION_FAILED=1
        return 1
    fi
    
    log_info "Configuration file found"
}

check_gambling_only_enabled() {
    log_info "Validating GAMBLING_ONLY setting..."
    
    # Source the config file
    if ! source "$CONFIG_FILE" 2>/dev/null; then
        log_error "Failed to source configuration file: $CONFIG_FILE"
        log_fatal "Configuration file may be malformed. Service startup blocked."
        VALIDATION_FAILED=1
        return 1
    fi
    
    # Check if GAMBLING_ONLY is set
    if [ -z "${GAMBLING_ONLY:-}" ]; then
        log_error "GAMBLING_ONLY variable not set in configuration"
        log_fatal "Required GAMBLING_ONLY setting is missing. Service startup blocked."
        VALIDATION_FAILED=1
        return 1
    fi
    
    # Check if GAMBLING_ONLY is set to 1
    if [ "$GAMBLING_ONLY" != "1" ]; then
        log_error "GAMBLING_ONLY is set to '$GAMBLING_ONLY' instead of '1'"
        log_fatal "System is not configured as gambling-only. Service startup blocked."
        VALIDATION_FAILED=1
        return 1
    fi
    
    log_info "GAMBLING_ONLY validation passed: $GAMBLING_ONLY"
}

check_allowed_detection_types() {
    log_info "Validating ALLOWED_DETECTION_TYPES setting..."
    
    # Check if ALLOWED_DETECTION_TYPES is set
    if [ -z "${ALLOWED_DETECTION_TYPES:-}" ]; then
        log_error "ALLOWED_DETECTION_TYPES variable not set in configuration"
        log_fatal "Required ALLOWED_DETECTION_TYPES setting is missing. Service startup blocked."
        VALIDATION_FAILED=1
        return 1
    fi
    
    # Check if ALLOWED_DETECTION_TYPES is set to gambling
    if [ "$ALLOWED_DETECTION_TYPES" != "gambling" ]; then
        log_error "ALLOWED_DETECTION_TYPES is set to '$ALLOWED_DETECTION_TYPES' instead of 'gambling'"
        log_fatal "Only gambling detection is permitted. Service startup blocked."
        VALIDATION_FAILED=1
        return 1
    fi
    
    log_info "ALLOWED_DETECTION_TYPES validation passed: $ALLOWED_DETECTION_TYPES"
}

################################################################################
# Main Validation Flow
################################################################################

main() {
    log_info "==== V-Sentinel Runtime Guard Starting ===="
    
    # Run all checks
    check_config_file_exists || true
    check_gambling_only_enabled || true
    check_allowed_detection_types || true
    
    if [ $VALIDATION_FAILED -eq 1 ]; then
        log_error "==== V-Sentinel Runtime Validation FAILED ===="
        log_fatal "Service startup blocked due to validation failure"
        exit 1
    fi
    
    log_info "==== All validations passed - Service startup approved ===="
    exit 0
}

# Run main validation
main
