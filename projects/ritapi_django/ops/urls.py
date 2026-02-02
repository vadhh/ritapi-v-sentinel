from django.urls import path, include
from . import views


urlpatterns = [
    path("", views.dashboard, name="ops_dashboard"),
    path("asn/", include("ops.ops_asn.urls")),
    path("ip-reputation/", include("ops.ops_iprep.urls")),
    path("json-schema/", include("ops.ops_json.urls")),
    path("alerts/", include("ops.ops_alert.urls")),
    path("blocked-ips/", include("ops.ops_blocking.urls")),
    path("geo-block/", include("ops.ops_geoblock.urls")),
    # path("tls/", views.tls_check, name="ops_tls"),
    # path("ip-reputation/", views.ip_reputation, name="ops_ip_reputation"),
    # path("request-log/", views.request_log, name="ops_request_log"),
    # path("alerts/", views.alert_list, name="ops_alerts"),
    # path("blocking/", views.blocking, name="ops_blocking"),
]