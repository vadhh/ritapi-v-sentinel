# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.requestlog_list, name="requestlog_list"),
    path("export/", views.export_requestlog_excel, name="export_requestlog_excel"),
    path("api/", views.requestlog_data, name="requestlog_data"),
    path("chart-data/", views.requestlog_chart_data, name="requestlog_chart_data"),
    # path("scan-logs/", views.scan_log_view, name="scan_log_view"),
]