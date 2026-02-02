# alert_blocking/alert_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.utils.timezone import now, timedelta

# Import model Alert
from alert.models import Alert
# Hapus import BlockingService karena tidak digunakan lagi di file ini

# ===================== ALERT MANAGEMENT =====================

def alert_dashboard(request):
    """Alert Management with search & filtering"""
    query = request.GET.get("q", "").strip()
    severity_filter = request.GET.get("severity", "")
    status_filter = request.GET.get("status", "")

    alerts = Alert.objects.all().order_by("-timestamp")

    # Flag to check if any filters are applied
    filters_applied = any([query, severity_filter, status_filter])

    # 🔍 Search by message or source IP
    if query:
        alerts = alerts.filter(
            Q(ip_address__icontains=query) |
            Q(alert_type__icontains=query) |
            Q(detail__icontains=query)
        )

    # 🎯 Filter by severity
    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)

    # Pagination
    paginator = Paginator(alerts, 10)
    page_number = request.GET.get("page")
    alerts_page = paginator.get_page(page_number)

    # Error message only shows if filters are applied
    error_message = None
    if filters_applied and not alerts.exists():
        error_message = "No alerts found with the given filters."

    return render(request, "ops_template/alerts.html", {
        "alerts": alerts_page,
        "query": query,
        "severity_filter": severity_filter,
        "status_filter": status_filter,
        "error_message": error_message
    })

def resolve_alert(request, alert_id):
    """Mark an alert as resolved"""
    alert = get_object_or_404(Alert, id=alert_id)
    alert.resolved = True
    alert.save()
    messages.success(request, f"Alert {alert.id} successfully resolved ✅")
    # Ganti 'ops_alert_dashboard' dengan nama view alert dashboard yang benar di urls.py Anda
    return redirect("ops_alert_dashboard")


# FUNGSI block_ip_from_alert DIHAPUS DARI FILE INI


def alert_chart_data(request):
    """Provide JSON data for the alert severity chart"""
    period = request.GET.get("period", "all")

    if period == "1d":
        start_date = now() - timedelta(days=1)
        alerts = Alert.objects.filter(timestamp__gte=start_date)
    elif period == "7d":
        start_date = now() - timedelta(days=7)
        alerts = Alert.objects.filter(timestamp__gte=start_date)
    elif period == "30d":
        start_date = now() - timedelta(days=30)
        alerts = Alert.objects.filter(timestamp__gte=start_date)
    else:
        alerts = Alert.objects.all()

    severity_labels = ["low", "medium", "high", "critical"]
    data = [alerts.filter(severity=s).count() for s in severity_labels]

    return JsonResponse({
        "labels": [s.capitalize() for s in severity_labels],
        "data": data,
    })