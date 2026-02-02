from django.urls import path
from . import views

urlpatterns = [
    # BLOCKED IPs
    path("", views.blocked_ip_dashboard, name="ops_blocked_ip_dashboard"),
    path("unblock/<str:ip_address>/", views.unblock_ip, name="ops_unblock_ip"),
    path("block/<str:ip_address>/", views.block_ip_manual, name="ops_block_ip_manual"),
    path("blocked-map/", views.blocked_ip_map, name="blocked_ip_map"),
    path("blocked-map/data/", views.blocked_ip_data, name="blocked_ip_data"),
]
