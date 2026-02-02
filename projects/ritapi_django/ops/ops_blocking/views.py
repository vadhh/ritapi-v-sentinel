# alert_blocking/blocking_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import JsonResponse

# Import model BlockedIP dan BlockingService
from blocking.models import BlockedIP
from blocking.services import BlockingService

# ===================== BLOCKED IP MANAGEMENT =====================

def blocked_ip_dashboard(request):
    """Blocked IP Management with search & filtering"""
    query = request.GET.get("q", "").strip()
    severity_filter = request.GET.get("severity", "")
    status_filter = request.GET.get("status", "")

    blocked_ips = BlockedIP.objects.all().order_by("-blocked_at")

    # Flag to check if any filters are applied
    filters_applied = any([query, severity_filter, status_filter])

    # 🔍 Search by IP
    if query:
        blocked_ips = blocked_ips.filter(ip_address__icontains=query)

    # 🎯 Filter by severity
    if severity_filter:
        blocked_ips = blocked_ips.filter(severity=severity_filter)

    # 🎯 Filter by status (active/inactive)
    if status_filter == "active":
        blocked_ips = blocked_ips.filter(active=True)
    elif status_filter == "inactive":
        blocked_ips = blocked_ips.filter(active=False)

    # Pagination
    paginator = Paginator(blocked_ips, 10)
    page_number = request.GET.get("page")
    blocked_page = paginator.get_page(page_number)

    # Error message only shows if filters are applied
    error_message = None
    if filters_applied and not blocked_ips.exists():
        error_message = "No blocked IPs found with the given filters."

    return render(request, "ops_template/blocked_ips.html", {
        "blocked_ips": blocked_page,
        "query": query,
        "severity_filter": severity_filter,
        "status_filter": status_filter,
        "error_message": error_message
    })

def block_ip_from_alert(request, ip_address):
    """Block IP directly, typically triggered from the Alert view/template"""
    # Menggunakan BlockingService
    BlockingService.block_ip(ip_address, reason="Blocked from alert", severity="high")
    messages.warning(request, f"IP {ip_address} successfully blocked 🚫")
    # Ganti 'ops_blocked_ip_dashboard' dengan nama view dashboard yang benar di urls.py Anda
    return redirect("ops_blocked_ip_dashboard")

def unblock_ip(request, ip_address):
    """Unblock IP"""
    blocked = BlockingService.unblock_ip(ip_address)
    if blocked:
        messages.success(request, f"IP {ip_address} successfully unblocked ✅")
    else:
        messages.error(request, f"IP {ip_address} not found ❌")
    return redirect("ops_blocked_ip_dashboard") # Ganti dengan nama view dashboard yang benar

def block_ip_manual(request, ip_address):
    """Manually re-block IP (default high severity permanent)."""
    blocked = BlockingService.block_ip(
        ip_address,
        reason="Manual block from dashboard",
        severity="high",
        duration_minutes=None  # permanent
    )
    if blocked:
        messages.warning(request, f"IP {ip_address} successfully re-blocked 🚫")
    else:
        messages.error(request, f"Failed to block IP {ip_address}")
    return redirect("ops_blocked_ip_dashboard") # Ganti dengan nama view dashboard yang benar

def blocked_ip_map(request):
    """
    Display interactive map of blocked IPs
    """
    return render(request, "ops_template/blocked_ip_map.html")

def blocked_ip_data(request):
    """
    JSON endpoint for map data (sent to Leaflet via fetch)
    """
    blocked = BlockedIP.objects.filter(
        active=True,
        latitude__isnull=False,
        longitude__isnull=False
    ).order_by("-blocked_at")

    data = [
        {
            "ip": b.ip_address,
            "country": b.country_name or b.country,
            "reason": b.reason,
            "severity": b.severity,
            "lat": b.latitude,
            "lon": b.longitude,
            "time": b.blocked_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for b in blocked
    ]

    return JsonResponse({"data": data})