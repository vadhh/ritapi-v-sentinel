import logging
import os
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from utils.ip import get_client_ip
from utils.json_request import enforce_json_request

# Utilitas yang HANYA diperlukan untuk Forwarding
from utils.proxy_forward import forward_request_to_backend 

logger = logging.getLogger(__name__)
MAX_JSON_BODY = getattr(settings, "MAX_JSON_BODY", 2 * 1024 * 1024)  # default 2 MB
ENFORCE_JSON_CT = getattr(settings, "ENFORCE_JSON_CT", True)

# Konfigurasi Target Backend (URL tujuan tunggal, diambil dari settings atau env)
TARGET_BACKEND_URL = getattr(
    settings, 
    "SINGLE_TARGET_BACKEND_URL", 
    os.getenv("SINGLE_TARGET_BACKEND_URL", "http://127.0.0.1:7003") 
).strip().strip('\'"')

# Placeholder ID, digunakan sebagai argumen ketiga untuk fungsi forward_request_to_backend 
# yang mungkin masih memerlukan sebuah nilai non-kosong, meskipun kita tidak menggunakannya untuk multi-service.
PROXY_ID_PLACEHOLDER = "single-tenant-proxy" 

def _safe_imports():
    mods = {}
    try:
        from alert.services import AlertService
        mods['AlertService'] = AlertService
    except ImportError:
        logger.warning("AlertService not found.")
    return mods

MODULES = _safe_imports()

class DecisionProxyMiddleware(MiddlewareMixin):
    """
    Middleware Reverse Proxy Murni (Forwarder) untuk Layanan Tunggal.
    Hanya meneruskan permintaan ke URL backend tetap yang dikonfigurasi.
    """

    def process_request(self, request):
        path = request.get_full_path()
        # Skip admin, static, dan path internal Django
        if (
            path == "/"   
            or path.startswith("/admin")
            or path.startswith("/static")
            or path.startswith("/__debug__")
            or path.startswith("/login")
            or path.startswith("/accounts/login")
            or path.startswith("/ops")
            or path.startswith("/logout")
            or path.startswith("/tls")
            or path.startswith("/healthz")
            or path.startswith("/readyz")
            or path.startswith("/demo")
            or path.startswith("/ai")
            or path.startswith("/change-password")
            or path.startswith("/metrics")
            or path == "/favicon.ico"
            or path == "/robots.txt"  
        ):
            # Jika salah satu path di atas, biarkan Django memprosesnya
            return None 
        # JSON enforcement pakai config
        content_type = request.META.get("CONTENT_TYPE", "").split(";")[0].strip().lower()
        if content_type.startswith("multipart/form-data"):
            from utils.file_validation import inspect_file_upload
            resp = inspect_file_upload(request, alert_module=MODULES.get("AlertService"))
            if resp:
                return resp
        else:
            # JSON enforcement pakai config
            resp = enforce_json_request(
                request,
                enforce_ct=ENFORCE_JSON_CT,
                max_body=MAX_JSON_BODY
            )
            if resp:
                return resp
        # body = request.body or b"" # Tidak diperlukan di sini
        
        # === Tentukan target backend (URL tetap)
        target_backend = TARGET_BACKEND_URL
            
        # === Forward to backend
        try:
            # Gunakan utilitas forwarding dengan target dan placeholder ID
            response = forward_request_to_backend(request, target_backend, PROXY_ID_PLACEHOLDER)
            
            # Kembalikan respons dari backend
            return response
            
        except Exception as e:
            logger.error(f"Error forwarding request to backend ({target_backend}): {e}")
            return JsonResponse({"error": "backend_unreachable", "detail": str(e)}, status=502)