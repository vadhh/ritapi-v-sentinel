from django.http import JsonResponse
import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.shortcuts import redirect

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")


@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(request):
    """Lightweight: hanya memastikan service hidup."""
    return JsonResponse(
        {
            "status": "ok",
            "app_version": APP_VERSION,
        }
    )


def home(request):
    """
    Redirect to dashboard if authenticated, otherwise to login
    """
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("ops_dashboard")
    else:
        return redirect("login")
