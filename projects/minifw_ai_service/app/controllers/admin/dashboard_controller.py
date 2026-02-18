from fastapi import Request
from fastapi.templating import Jinja2Templates
from datetime import datetime
import subprocess
import json
import os

from app.services.allow_domain.get_allow_domains_service import get_allow_domains
from app.services.deny_ip.get_deny_ips_service import get_deny_ips
from app.services.deny_asn.get_deny_asns_service import get_deny_asns
from app.services.deny_domain.get_deny_domains_service import get_deny_domains
from app.services.events.get_events_service import (
    get_recent_events,
    get_event_statistics,
    get_system_uptime,
)

templates = Jinja2Templates(directory="app/web/templates")


def get_service_status():
    """
    Check if the minifw_ai service is running and get its mode.
    Returns a dict with label, color, and mode.
    """
    status = {"label": "Stopped", "color": "danger", "mode": "Unknown"}

    # 1. Check if process is running
    try:
        # pgrep -f "python -m minifw_ai" (matches the command used in systemd)
        subprocess.check_call(
            ["pgrep", "-f", "python -m minifw_ai"], stdout=subprocess.DEVNULL
        )
        status["label"] = "Active"
        status["color"] = "success"
    except subprocess.CalledProcessError:
        status["label"] = "Stopped"
        status["color"] = "danger"

    # 2. Check deployment mode from state file
    state_file = "/var/log/ritapi/deployment_state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
                # "dns_telemetry": { "status": "BASELINE_PROTECTION" ... }
                dns_status = data.get("dns_telemetry", {}).get("status", "Unknown")
                status["mode"] = dns_status.replace("_", " ").title()
        except Exception:
            status["mode"] = "Error reading state"
    else:
        status["mode"] = " ongoing..."

    return status


def dashboard_controller(request: Request):
    """
    Dashboard controller for Minifw-AI
    Shows statistics and recent events
    """

    # Get counts from all firewall rules
    allow_domains = len(get_allow_domains())
    deny_ips = len(get_deny_ips())
    deny_asns = len(get_deny_asns())
    deny_domains = len(get_deny_domains())

    # Get events and statistics
    events = get_recent_events(limit=5)
    event_stats = get_event_statistics()
    uptime = get_system_uptime()

    # Get service status
    service_status = get_service_status()

    # Calculate total rules
    total_rules = allow_domains + deny_ips + deny_asns + deny_domains

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": {"name": "Fahrezi"},
            "stats": {
                "allow_domains": allow_domains,
                "deny_ips": deny_ips,
                "deny_asns": deny_asns,
                "deny_domains": deny_domains,
                "total_rules": total_rules,
                "total_allowed": event_stats["total_allowed"],
                "total_blocked": event_stats["total_blocked"],
                "threats_detected": event_stats["threats_detected"],
                "uptime": uptime,
            },
            "service_status": service_status,
            "events": events,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def get_dashboard_stats():
    """
    Helper function to get dashboard statistics
    Can be called from API endpoints
    """
    allow_domains = len(get_allow_domains())
    deny_ips = len(get_deny_ips())
    deny_asns = len(get_deny_asns())
    deny_domains = len(get_deny_domains())
    event_stats = get_event_statistics()
    service_status = get_service_status()

    return {
        "firewall_rules": {
            "allow_domains": allow_domains,
            "deny_ips": deny_ips,
            "deny_asns": deny_asns,
            "deny_domains": deny_domains,
            "total_rules": allow_domains + deny_ips + deny_asns + deny_domains,
        },
        "events": {
            "total_allowed": event_stats["total_allowed"],
            "total_blocked": event_stats["total_blocked"],
            "threats_detected": event_stats["threats_detected"],
        },
        "system": {"uptime": get_system_uptime(), "status": service_status},
    }
