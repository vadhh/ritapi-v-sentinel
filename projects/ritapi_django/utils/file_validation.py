import mimetypes
import os
from django.http import JsonResponse
from utils.severity import determine_severity
import logging
from utils.telegram_notif import send_telegram_message


logger = logging.getLogger(__name__)

# === Configurable constants ===
ALLOWED_MIME = {"image/png", "image/jpeg", "application/pdf"}
MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB
FORBIDDEN_EXT = {".php", ".js", ".jsp", ".exe", ".sh", ".bat"}


def inspect_file_upload(request, alert_module=None):
    """
    Validasi file upload (multipart/form-data)
    - MIME allowlist
    - Max size limit
    - Reject PHP/JS extensions
    - Kirim alert otomatis jika ada pelanggaran
    """
    files = getattr(request, "FILES", None)
    # if not files or len(files) == 0:
    #     return JsonResponse({"error": "No file uploaded."}, status=400)

    for name, f in files.items():
        mime = getattr(f, "content_type", None)
        filename = getattr(f, "name", "unknown")
        file_size = getattr(f, "size", 0)

        # === 1. Forbidden extension check ===
        if any(filename.lower().endswith(ext) for ext in FORBIDDEN_EXT):
            reason = f"Forbidden file extension: {filename}"
            sev = determine_severity(reason, score=80)
            logger.warning(reason)
            if alert_module:
                try:
                    alert_module.create_alert(
                        alert_type="UPLOAD_BLOCKED",
                        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                        detail=reason,
                        severity=sev,
                    )
                    send_telegram_message(
                        alert_type="UPLOAD_BLOCKED",
                        client_ip=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                        severity=sev,
                        reason=reason,
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert for forbidden file: {e}")
            return JsonResponse({"error": reason}, status=415)

        # === 2. MIME type validation ===
        if mime not in ALLOWED_MIME:
            reason = f"Unsupported MIME type: {mime} ({filename})"
            sev = determine_severity(reason, score=50)
            logger.warning(reason)
            if alert_module:
                try:
                    alert_module.create_alert(
                        alert_type="UPLOAD_UNSUPPORTED_MIME",
                        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                        detail=reason,
                        severity=sev,
                    )
                    send_telegram_message(
                        alert_type="UPLOAD_UNSUPPORTED_MIME",
                        client_ip=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                        severity=sev,
                        reason=reason,
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert for MIME violation: {e}")
            return JsonResponse({"error": reason}, status=415)

        # === 3. File size limit ===
        if file_size > MAX_UPLOAD_SIZE:
            reason = f"File too large ({file_size} bytes) for {filename}"
            sev = determine_severity(reason, score=40)
            logger.warning(reason)
            if alert_module:
                try:
                    alert_module.create_alert(
                        alert_type="UPLOAD_TOO_LARGE",
                        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                        detail=reason,
                        severity=sev,
                    )
                    send_telegram_message(
                        alert_type="UPLOAD_TOO_LARGE",
                        client_ip=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                        severity=sev,
                        reason=reason,
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert for file size: {e}")
            return JsonResponse({"error": reason}, status=413)

    logger.info(f"✅ All uploaded files passed validation ({len(files)} file(s))")
    return None
