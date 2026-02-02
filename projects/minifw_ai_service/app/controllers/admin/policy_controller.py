from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.services.policy.get_policy_service import (
    get_policy,
    get_segments,
    get_segment_subnets,
    get_features,
    get_enforcement,
    get_collectors,
    get_burst
)
from app.services.policy.update_policy_service import (
    update_segment,
    delete_segment,
    update_segment_subnets,
    update_features,
    update_enforcement,
    update_collectors,
    update_burst
)

templates = Jinja2Templates(directory="app/web/templates")


def policy_controller(request: Request):
    """Display policy configuration page"""
    try:
        policy = get_policy()
        segments = get_segments()
        segment_subnets = get_segment_subnets()
        features = get_features()
        enforcement = get_enforcement()
        collectors = get_collectors()
        burst = get_burst()
        
        return templates.TemplateResponse(
            "admin/policy.html",
            {
                "request": request,
                "policy": policy,
                "segments": segments,
                "segment_subnets": segment_subnets,
                "features": features,
                "enforcement": enforcement,
                "collectors": collectors,
                "burst": burst,
                "user": {"name": "Admin"}
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def add_segment_controller(segment_name: str, block_threshold: int, monitor_threshold: int):
    """Add or update a segment"""
    try:
        update_segment(segment_name, block_threshold, monitor_threshold)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def delete_segment_controller(segment_name: str):
    """Delete a segment"""
    try:
        delete_segment(segment_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_segment_subnets_controller(segment_name: str, subnets: list):
    """Update segment subnets"""
    try:
        update_segment_subnets(segment_name, subnets)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_features_controller(dns_weight: int, sni_weight: int, asn_weight: int, burst_weight: int):
    """Update feature weights"""
    try:
        update_features(dns_weight, sni_weight, asn_weight, burst_weight)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_enforcement_controller(ipset_name_v4: str, ip_timeout_seconds: int, nft_table: str, nft_chain: str):
    """Update enforcement configuration"""
    try:
        update_enforcement(ipset_name_v4, ip_timeout_seconds, nft_table, nft_chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_collectors_controller(dnsmasq_log_path: str, zeek_ssl_log_path: str, use_zeek_sni: bool):
    """Update collectors configuration"""
    try:
        update_collectors(dnsmasq_log_path, zeek_ssl_log_path, use_zeek_sni)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_burst_controller(dns_queries_per_minute_monitor: int, dns_queries_per_minute_block: int):
    """Update burst detection configuration"""
    try:
        update_burst(dns_queries_per_minute_monitor, dns_queries_per_minute_block)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
