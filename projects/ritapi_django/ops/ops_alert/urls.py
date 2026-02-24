from django.urls import path
from . import views

urlpatterns = [
    # ALERTS
    path("", views.alert_dashboard, name="ops.ops_alert"),
    path("resolve/<int:alert_id>/", views.resolve_alert, name="ops_resolve_alert"),
    path("alert_chart_data/", views.alert_chart_data, name="alert_chart_data"),
]
