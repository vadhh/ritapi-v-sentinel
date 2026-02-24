"""
Sector Policy Configuration

Defines sector-specific security policies and behaviors.
Each sector has unique requirements based on industry regulations and threat models.
"""

from __future__ import annotations
from typing import Dict, Any, List

# Import SectorType - handle potential circular import
try:
    from app.models.user import SectorType
except ImportError:
    # Fallback for standalone testing
    from enum import Enum

    class SectorType(str, Enum):
        HOSPITAL = "hospital"
        SCHOOL = "school"
        GOVERNMENT = "government"
        FINANCE = "finance"
        LEGAL = "legal"
        ESTABLISHMENT = "establishment"


# ============================================================================
# SECTOR POLICY DEFINITIONS
# ============================================================================

SECTOR_POLICIES: Dict[SectorType, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # SCHOOL SECTOR
    # Focus: Content filtering, SafeSearch, VPN/Proxy blocking
    # -------------------------------------------------------------------------
    SectorType.SCHOOL: {
        "description": "Education: Enforces SafeSearch and strict content filtering.",
        # SafeSearch enforcement (requires dnsmasq config)
        "force_safesearch": True,
        "safesearch_domains": [
            "google.com",
            "bing.com",
            "youtube.com",
            "duckduckgo.com",
        ],
        # VPN/Proxy blocking
        "block_vpns": True,
        "block_proxies": True,
        # Additional threat feeds
        "extra_feeds": ["school_blacklist.txt"],
        # Stricter thresholds
        "block_threshold_adjustment": -10,  # Block 10 points sooner
        "monitor_threshold_adjustment": -10,
        # Logging
        "strict_logging": True,
        "log_student_activity": True,
    },
    # -------------------------------------------------------------------------
    # HOSPITAL SECTOR (HIPAA Compliant)
    # Focus: IoMT device protection, minimal PII logging
    # -------------------------------------------------------------------------
    SectorType.HOSPITAL: {
        "description": "Healthcare: Prioritizes IoMT device anomaly detection.",
        # IoMT (Internet of Medical Things) protection
        "iomt_high_priority": True,
        "iomt_alert_on_anomaly": True,
        # HIPAA compliance: Don't log payload/PII data
        "strict_pii_logging": False,
        "redact_payloads": True,
        # Much stricter anomaly detection for medical network
        "monitor_threshold_adjustment": -20,  # Alert on even minor anomalies
        "block_threshold_adjustment": -5,
        # Additional threat feeds
        "extra_feeds": ["healthcare_threats.txt"],
        # Medical device network alerting
        "alert_severity_boost": "critical",  # All IoMT alerts are critical
    },
    # -------------------------------------------------------------------------
    # GOVERNMENT SECTOR
    # Focus: Geo-IP restrictions, strict audit logging, APT detection
    # -------------------------------------------------------------------------
    SectorType.GOVERNMENT: {
        "description": "Government: Strict Geo-IP and long-term audit logging.",
        # Geo-IP restrictions
        "geo_ip_strict": True,
        "blocked_countries": ["KP", "IR", "RU", "CN"],  # Configurable via policy.json
        # Extended audit logging
        "strict_logging": True,
        "log_retention_days": 365,  # 1 year minimum
        "audit_all_queries": True,
        # APT detection focus
        "apt_detection_mode": True,
        # Additional threat feeds
        "extra_feeds": ["government_sensitive.txt", "apt_indicators.txt"],
        # Threshold adjustments
        "block_threshold_adjustment": -5,
        "monitor_threshold_adjustment": -10,
    },
    # -------------------------------------------------------------------------
    # FINANCE SECTOR (PCI-DSS Focus)
    # Focus: Fraud prevention, strict TLS, Tor blocking
    # -------------------------------------------------------------------------
    SectorType.FINANCE: {
        "description": "Finance: PCI-DSS compliance focus and anti-fraud.",
        # Tor and anonymizer blocking (fraud prevention)
        "block_tor": True,
        "block_anonymizers": True,
        # Strict TLS enforcement
        "strict_tls": True,
        "minimum_tls_version": "1.2",
        # PCI-DSS compliance mode
        "pci_compliance_mode": True,
        # Additional threat feeds
        "extra_feeds": ["financial_fraud.txt", "crypto_scams.txt"],
        # Threshold adjustments
        "block_threshold_adjustment": -5,
        "monitor_threshold_adjustment": -5,
        # Logging (PCI requires detailed logs)
        "strict_logging": True,
        "log_retention_days": 90,
    },
    # -------------------------------------------------------------------------
    # LEGAL SECTOR
    # Focus: Data exfiltration detection, confidentiality
    # -------------------------------------------------------------------------
    SectorType.LEGAL: {
        "description": "Legal: High sensitivity to data exfiltration patterns.",
        # Data exfiltration detection
        "data_exfiltration_watch": True,
        "large_upload_alert": True,
        "large_upload_threshold_mb": 50,
        # Confidentiality mode
        "confidentiality_mode": True,
        # Additional threat feeds
        "extra_feeds": ["legal_threats.txt"],
        # Threshold adjustments
        "block_threshold_adjustment": 0,
        "monitor_threshold_adjustment": -10,
        # Logging
        "strict_logging": True,
        "log_retention_days": 180,
    },
    # -------------------------------------------------------------------------
    # ESTABLISHMENT SECTOR (SME/Retail - Balanced)
    # Focus: Standard protection, balanced defaults
    # -------------------------------------------------------------------------
    SectorType.ESTABLISHMENT: {
        "description": "Establishment: Balanced protection for SMEs and Retail.",
        # Standard protection
        "standard_protection": True,
        # No extreme threshold adjustments
        "block_threshold_adjustment": 0,
        "monitor_threshold_adjustment": 0,
        # Standard feeds (no extras)
        "extra_feeds": [],
        # Logging
        "strict_logging": False,
        "log_retention_days": 30,
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_sector_policy(sector: SectorType) -> Dict[str, Any]:
    """Get policy configuration for a given sector."""
    return SECTOR_POLICIES.get(sector, SECTOR_POLICIES[SectorType.ESTABLISHMENT])


def get_threshold_adjustment(sector: SectorType, threshold_type: str = "block") -> int:
    """
    Get threshold adjustment for a sector.

    Args:
        sector: The sector to get adjustment for
        threshold_type: Either "block" or "monitor"

    Returns:
        Integer adjustment value (negative means stricter)
    """
    policy = get_sector_policy(sector)
    key = f"{threshold_type}_threshold_adjustment"
    return policy.get(key, 0)


def get_extra_feeds(sector: SectorType) -> List[str]:
    """Get list of additional feed files for a sector."""
    policy = get_sector_policy(sector)
    return policy.get("extra_feeds", [])


def should_force_safesearch(sector: SectorType) -> bool:
    """Check if sector requires SafeSearch enforcement."""
    policy = get_sector_policy(sector)
    return policy.get("force_safesearch", False)


def should_block_vpns(sector: SectorType) -> bool:
    """Check if sector requires VPN blocking."""
    policy = get_sector_policy(sector)
    return policy.get("block_vpns", False)


def is_iomt_priority(sector: SectorType) -> bool:
    """Check if sector has IoMT high-priority alerting."""
    policy = get_sector_policy(sector)
    return policy.get("iomt_high_priority", False)
