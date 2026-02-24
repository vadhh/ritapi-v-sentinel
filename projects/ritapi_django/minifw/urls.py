"""
URLs untuk MiniFW-AI Configuration
"""

from django.urls import path
from . import views

urlpatterns = [
    # Main Pages
    path("dashboard/", views.minifw_dashboard, name="minifw_dashboard"),
    path("policy/", views.minifw_policy, name="minifw_policy"),
    path("feeds/", views.minifw_feeds, name="minifw_feeds"),
    path("blocked-ips/", views.minifw_blocked_ips, name="minifw_blocked_ips"),
    path("audit-logs/", views.minifw_audit_logs, name="minifw_audit_logs"),
    path("events/", views.minifw_events, name="minifw_events"),
    path("users/", views.minifw_users, name="minifw_users"),
    # Service Control
    path(
        "service/control/", views.minifw_service_control, name="minifw_service_control"
    ),
    # API — Stats / Service
    path("api/stats/", views.minifw_api_stats, name="minifw_api_stats"),
    path(
        "api/service-status/",
        views.minifw_api_service_status,
        name="minifw_api_service_status",
    ),
    path(
        "api/events/", views.minifw_api_recent_events, name="minifw_api_recent_events"
    ),
    # API — Events (DataTables + Export)
    path(
        "api/events/datatable/",
        views.minifw_api_events_datatable,
        name="minifw_api_events_datatable",
    ),
    path(
        "api/events/export/",
        views.minifw_api_events_export,
        name="minifw_api_events_export",
    ),
    # API — Audit Logs
    path("api/audit/logs/", views.minifw_api_audit_logs, name="minifw_api_audit_logs"),
    path(
        "api/audit/statistics/",
        views.minifw_api_audit_statistics,
        name="minifw_api_audit_statistics",
    ),
    path(
        "api/audit/export/",
        views.minifw_api_audit_export,
        name="minifw_api_audit_export",
    ),
    # API — User Management
    path("api/users/", views.minifw_api_users_list, name="minifw_api_users_list"),
    path(
        "api/users/create/",
        views.minifw_api_users_create,
        name="minifw_api_users_create",
    ),
    path(
        "api/users/<int:user_id>/",
        views.minifw_api_users_update,
        name="minifw_api_users_update",
    ),
    path(
        "api/users/<int:user_id>/password/",
        views.minifw_api_users_password,
        name="minifw_api_users_password",
    ),
    path(
        "api/users/<int:user_id>/delete/",
        views.minifw_api_users_delete,
        name="minifw_api_users_delete",
    ),
    # API — Current User / Sector Lock / Deployment State
    path(
        "api/auth/current-user/",
        views.minifw_api_current_user,
        name="minifw_api_current_user",
    ),
    path(
        "api/sector-lock/", views.minifw_api_sector_lock, name="minifw_api_sector_lock"
    ),
    path(
        "api/deployment-state/",
        views.minifw_api_deployment_state,
        name="minifw_api_deployment_state",
    ),
]
