import json
import os
from typing import Dict, Any

def get_policy() -> Dict[str, Any]:
    """Get complete policy configuration"""
    policy_path = os.environ.get("MINIFW_POLICY", "config/policy.json")
    
    try:
        with open(policy_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Policy file not found: {policy_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in policy file: {policy_path}")

def get_segments() -> Dict[str, Any]:
    """Get all segments configuration"""
    policy = get_policy()
    return policy.get("segments", {})

def get_segment_subnets() -> Dict[str, list]:
    """Get segment to subnet mappings"""
    policy = get_policy()
    return policy.get("segment_subnets", {})

def get_features() -> Dict[str, int]:
    """Get feature weights"""
    policy = get_policy()
    return policy.get("features", {})

def get_enforcement() -> Dict[str, Any]:
    """Get enforcement configuration"""
    policy = get_policy()
    return policy.get("enforcement", {})

def get_collectors() -> Dict[str, Any]:
    """Get collectors configuration"""
    policy = get_policy()
    return policy.get("collectors", {})

def get_burst() -> Dict[str, int]:
    """Get burst detection configuration"""
    policy = get_policy()
    return policy.get("burst", {})
