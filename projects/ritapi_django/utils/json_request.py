import json
import unicodedata
import logging
from django.conf import settings
from django.http import JsonResponse
from utils.logging import log_request  # Import log_request yang sudah disesuaikan

logger = logging.getLogger(__name__)

def enforce_json_request(request, enforce_ct=True, max_body=1 * 1024 * 1024):
    
    """
    Validasi request JSON.
    - Enforce Content-Type
    - Limit body size
    - Decode UTF-8 + normalize
    - Parse JSON ke request.json
    - Skip untuk path non-API (admin, login, static, dll.)
    """
    # Load excluded paths from settings
    excluded_paths = getattr(settings, "SECURITY_ENFORCEMENT_EXCLUDED_PATHS", [])
    
    # Skip enforcement untuk path tertentu
    if any(request.path.startswith(p) for p in excluded_paths):
        request.json = None
        return None

    # --- common variables for logging ---
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client_ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")
    path = request.path
    body = getattr(request, "body", b"") or b""

    if request.method in ["POST", "PUT", "PATCH"]:
        # 1. Enforce Content-Type JSON
        if enforce_ct:
            ct = request.META.get("CONTENT_TYPE", "").split(";")[0].strip()
            if ct != "application/json":
                logger.warning(f"Blocked: invalid Content-Type {ct}")
                try:
                    log_request(
                        ip=client_ip,
                        path=path,
                        method=request.method,
                        size=len(body),
                        score=0.0, # Skor risiko rendah untuk kesalahan format
                        action="block",
                        reasons="INVALID_CONTENT_TYPE",
                        label="format_violation",
                    )
                except Exception:
                    logger.exception("log_request failed")
                return JsonResponse(
                    {"error": "Unsupported Content-Type. Use application/json."},
                    status=415
                )

        # 2. Body size limit
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                content_length = int(content_length)
            except ValueError:
                content_length = 0

            if content_length > max_body:
                logger.warning(f"Blocked: content length too large ({content_length} bytes)")
                try:
                    log_request(
                        ip=client_ip,
                        path=path,
                        method=request.method,
                        size=content_length,
                        score=0.0,
                        action="block",
                        reasons="BODY_TOO_LARGE",
                        label="size_violation",    
                    )
                except Exception:
                    logger.exception("log_request failed")
                return JsonResponse(
                    {"error": "Request body too large."}, status=413
                )

        # 3. Parse JSON safely
        if request.body:
            try:
                raw_body = request.body.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning("Blocked: invalid UTF-8 encoding")
                try:
                    log_request(
                        ip=client_ip,
                        path=path,
                        method=request.method,
                        size=len(body),
                        score=0.0,
                        action="block",
                        reasons="INVALID_ENCODING",
                        label="encoding_violation",
                    )
                except Exception:
                    logger.exception("log_request failed")
                return JsonResponse(
                    {"error": "Invalid encoding. Expect UTF-8."}, status=400
                )

            normalized_body = unicodedata.normalize("NFC", raw_body)

            try:
                request.json = json.loads(normalized_body)
                # --- Additional Security Checks ---
                if isinstance(request.json, dict):

                    # 1. Detect dangerous literals like "rm -rf"
                    DANGEROUS = ["rm -rf", "rm -rf /", "rm -fr", "chmod 777", "wget http", "curl http"]
                    json_str = normalized_body.lower()

                    if any(d in json_str for d in DANGEROUS):
                        logger.warning("Blocked: dangerous literal detected")
                        log_request(
                            ip=client_ip,
                            path=path,
                            method=request.method,
                            size=len(body),
                            score=0.9, # Skor risiko tinggi
                            action="block",
                            reasons="DANGEROUS_LITERAL",
                            label="waf_injection",
                        )
                        return JsonResponse(
                            {"error": "Dangerous content detected."}, status=400
                        )

                    # 2. Detect inconsistent types (string → int attack)
                    def detect_inconsistent_types(obj):
                        for k, v in obj.items():
                            # Case 1: Numeric-looking string
                            if isinstance(v, str) and v.isdigit():
                                return k, v, "numeric_string"

                            # Case 2: Boolean-looking string
                            if isinstance(v, str) and v.lower() in ["true", "false"]:
                                return k, v, "bool_string"

                            # Case 3: Nested objects
                            if isinstance(v, dict):
                                result = detect_inconsistent_types(v)
                                if result:
                                    return result

                            # Case 4: Lists
                            if isinstance(v, list):
                                for item in v:
                                    if isinstance(item, dict):
                                        result = detect_inconsistent_types(item)
                                        if result:
                                            return result

                        return None

                    inconsistent = detect_inconsistent_types(request.json)
                    if inconsistent:
                        field, value, issue = inconsistent
                        logger.warning(f"Blocked: inconsistent type detected in field '{field}' with value '{value}'")
                        log_request(
                            ip=client_ip,
                            path=path,
                            method=request.method,
                            size=len(body),
                            score=0.5, # Skor risiko menengah
                            action="block",
                            reasons=f"INCONSISTENT_TYPE_{issue.upper()}",
                            label="type_smuggling",
                        )
                        return JsonResponse(
                            {"error": f"Inconsistent type detected in field '{field}'."},
                            status=400
                        )
            except json.JSONDecodeError:
                logger.warning("Blocked: malformed JSON body")
                try:
                    log_request(
                        ip=client_ip,
                        path=path,
                        method=request.method,
                        size=len(body),
                        score=0.0,
                        action="block",
                        reasons="MALFORMED_JSON",
                        label="format_violation",
                    )
                except Exception:
                    logger.exception("log_request failed")
                return JsonResponse(
                    {"error": "Malformed JSON body."}, status=400
                )
        else:
            request.json = {}
    else:
        # GET / DELETE / HEAD → no body
        request.json = None

    return None