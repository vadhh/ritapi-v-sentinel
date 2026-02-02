from django.urls import path
from .views import (
    BlockIPView,
    UnblockIPView,
    CheckIPView,
    ListBlockedIPsView,
)

urlpatterns = [
    path("block/", BlockIPView.as_view(), name="block-ip"),
    path("unblock/", UnblockIPView.as_view(), name="unblock-ip"),
    path("check/<str:ip_address>/", CheckIPView.as_view(), name="check-ip"),
    path("blocked/", ListBlockedIPsView.as_view(), name="list-blocked"),
]