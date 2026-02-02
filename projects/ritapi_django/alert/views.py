# alerts/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import AlertService
from .models import Alert

class CreateAlertView(APIView):
    """
    Buat alert baru. Severity otomatis ditentukan jika tidak dikirim.
    Email & Telegram dikirim jika severity high/critical.
    """
    def post(self, request):
        data = request.data
        alert = AlertService.create_alert(
            alert_type=data.get("alert_type"),
            ip_address=data.get("ip_address"),
            detail=data.get("detail"),
            severity=data.get("severity"),  # biarkan None jika ingin auto-detect
        )
        return Response(
            {"message": "Alert created", "id": alert.id},
            status=status.HTTP_201_CREATED
        )


class ListAlertsView(APIView):
    """
    Ambil 10 alert terakhir.
    """
    def get(self, request):
        alerts = Alert.objects.all().order_by("-timestamp")[:10]
        return Response([
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "ip_address": a.ip_address,
                "severity": a.severity,
                "detail": a.detail,
                "resolved": a.resolved,
                "timestamp": a.timestamp,
            }
            for a in alerts
        ])
