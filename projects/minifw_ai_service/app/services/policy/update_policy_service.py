import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any


def _backup_policy():
    """Create backup of current policy"""
    policy_path = os.environ.get("MINIFW_POLICY", "config/policy.json")
    if os.path.exists(policy_path):
        backup_path = f"{policy_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(policy_path, backup_path)
        return backup_path
    return None


def _save_policy(policy_data: Dict[str, Any]):
    """Save policy to file using atomic write-and-rename"""
    policy_path = os.environ.get("MINIFW_POLICY", "config/policy.json")

    # Create backup first
    _backup_policy()

    # Atomic Write: Write to unique .tmp, fsync, then rename
    import uuid

    temp_path = f"{policy_path}.{uuid.uuid4()}.tmp"
    try:
        with open(temp_path, "w") as f:
            json.dump(policy_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.rename(temp_path, policy_path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


def update_segment(segment_name: str, block_threshold: int, monitor_threshold: int):
    """Update or add a segment configuration"""
    from app.services.policy.get_policy_service import get_policy

    if not segment_name:
        raise ValueError("Segment name is required")

    if not (0 <= block_threshold <= 100):
        raise ValueError("Block threshold must be between 0 and 100")

    if not (0 <= monitor_threshold <= 100):
        raise ValueError("Monitor threshold must be between 0 and 100")

    if monitor_threshold >= block_threshold:
        raise ValueError("Monitor threshold must be less than block threshold")

    policy = get_policy()

    if "segments" not in policy:
        policy["segments"] = {}

    policy["segments"][segment_name] = {
        "block_threshold": block_threshold,
        "monitor_threshold": monitor_threshold,
    }

    _save_policy(policy)


def delete_segment(segment_name: str):
    """Delete a segment configuration"""
    from app.services.policy.get_policy_service import get_policy

    if segment_name == "default":
        raise ValueError("Cannot delete default segment")

    policy = get_policy()

    if "segments" not in policy or segment_name not in policy["segments"]:
        raise ValueError(f"Segment '{segment_name}' not found")

    del policy["segments"][segment_name]

    # Also remove from segment_subnets if exists
    if "segment_subnets" in policy and segment_name in policy["segment_subnets"]:
        del policy["segment_subnets"][segment_name]

    _save_policy(policy)


def update_segment_subnets(segment_name: str, subnets: list):
    """Update subnet mappings for a segment"""
    from app.services.policy.get_policy_service import get_policy
    import ipaddress

    if not segment_name:
        raise ValueError("Segment name is required")

    # Validate subnets
    for subnet in subnets:
        try:
            ipaddress.ip_network(subnet)
        except ValueError:
            raise ValueError(f"Invalid subnet format: {subnet}")

    policy = get_policy()

    # Check if segment exists
    if "segments" not in policy or segment_name not in policy["segments"]:
        raise ValueError(
            f"Segment '{segment_name}' does not exist. Create segment first."
        )

    if "segment_subnets" not in policy:
        policy["segment_subnets"] = {}

    if subnets:
        policy["segment_subnets"][segment_name] = subnets
    else:
        # Remove empty subnet mapping
        if segment_name in policy["segment_subnets"]:
            del policy["segment_subnets"][segment_name]

    _save_policy(policy)


def update_features(
    dns_weight: int, sni_weight: int, asn_weight: int, burst_weight: int
):
    """Update feature weights"""
    from app.services.policy.get_policy_service import get_policy

    # Validate weights
    for weight in [dns_weight, sni_weight, asn_weight, burst_weight]:
        if not (0 <= weight <= 100):
            raise ValueError("All weights must be between 0 and 100")

    total = dns_weight + sni_weight + asn_weight + burst_weight
    if total != 100:
        raise ValueError(f"Weights must sum to 100 (current sum: {total})")

    policy = get_policy()

    policy["features"] = {
        "dns_weight": dns_weight,
        "sni_weight": sni_weight,
        "asn_weight": asn_weight,
        "burst_weight": burst_weight,
    }

    _save_policy(policy)


def update_enforcement(
    ipset_name_v4: str, ip_timeout_seconds: int, nft_table: str, nft_chain: str
):
    """Update enforcement configuration"""
    from app.services.policy.get_policy_service import get_policy

    if not ipset_name_v4:
        raise ValueError("IPSet name is required")

    if ip_timeout_seconds < 0:
        raise ValueError("IP timeout must be non-negative")

    policy = get_policy()

    policy["enforcement"] = {
        "ipset_name_v4": ipset_name_v4,
        "ip_timeout_seconds": ip_timeout_seconds,
        "nft_table": nft_table,
        "nft_chain": nft_chain,
    }

    _save_policy(policy)


def update_collectors(
    dnsmasq_log_path: str, zeek_ssl_log_path: str, use_zeek_sni: bool
):
    """Update collectors configuration"""
    from app.services.policy.get_policy_service import get_policy

    # Security: Validate paths using whitelist and realpath
    # Use pathlib to prevent partial path traversal (e.g., /tmp_hack vs /tmp/)
    from pathlib import Path

    allowed_prefixes = [Path(p) for p in ("/var/log", "/opt/minifw_ai", "/tmp")]

    for path in [dnsmasq_log_path, zeek_ssl_log_path]:
        resolved = Path(os.path.realpath(path))
        is_allowed = False
        for prefix in allowed_prefixes:
            try:
                # is_relative_to is available in Python 3.9+
                if resolved.is_relative_to(prefix):
                    is_allowed = True
                    break
            except AttributeError:
                # Fallback for Python < 3.9
                try:
                    resolved.relative_to(prefix)
                    is_allowed = True
                    break
                except ValueError:
                    continue

        if not is_allowed:
            raise ValueError(
                f"Security Error: Path '{path}' is not allowed. Must accept: {allowed_prefixes}"
            )

    policy = get_policy()

    policy["collectors"] = {
        "dnsmasq_log_path": dnsmasq_log_path,
        "zeek_ssl_log_path": zeek_ssl_log_path,
        "use_zeek_sni": use_zeek_sni,
    }

    _save_policy(policy)


def update_burst(
    dns_queries_per_minute_monitor: int, dns_queries_per_minute_block: int
):
    """Update burst detection configuration"""
    from app.services.policy.get_policy_service import get_policy

    if dns_queries_per_minute_monitor < 0 or dns_queries_per_minute_block < 0:
        raise ValueError("Query limits must be non-negative")

    if dns_queries_per_minute_monitor >= dns_queries_per_minute_block:
        raise ValueError("Monitor threshold must be less than block threshold")

    policy = get_policy()

    policy["burst"] = {
        "dns_queries_per_minute_monitor": dns_queries_per_minute_monitor,
        "dns_queries_per_minute_block": dns_queries_per_minute_block,
    }

    _save_policy(policy)
