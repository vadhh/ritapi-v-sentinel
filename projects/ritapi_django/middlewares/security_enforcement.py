import logging
import os
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger(__name__)

# Configurable constants from settings
MAX_JSON_BODY = getattr(settings, "MAX_JSON_BODY", 2 * 1024 * 1024)
ENFORCE_JSON_CT = getattr(settings, "ENFORCE_JSON_CT", True)


def _safe_imports():
    mods = {}
    try:
        # Import dynamically to avoid circular dependencies
        from alert.services import AlertService

        mods["AlertService"] = AlertService
    except ImportError:
        logger.warning("AlertService not found.")
    except Exception as e:
        logger.warning(f"Could not import AlertService: {e}")
    return mods


# Pre-load modules for performance
MODULES = _safe_imports()


class SecurityEnforcementMiddleware(MiddlewareMixin):
    """
    Middleware for Unified Security Enforcement.
    Handles JSON validation and file upload inspection for all Django routes
    (except those whitelisted in utils/json_request.py).

    Architecture B: Forwarding to port 7003 is removed in favor of a unified dashboard.
    """

    def process_request(self, request):
        content_type = (
            request.META.get("CONTENT_TYPE", "").split(";")[0].strip().lower()
        )

        # 1. File upload inspection (multipart/form-data)
        if content_type.startswith("multipart/form-data"):
            from utils.file_validation import inspect_file_upload

            return inspect_file_upload(
                request, alert_module=MODULES.get("AlertService")
            )

        # 2. JSON enforcement (application/json)
        # The enforce_json_request function handles its own path whitelist.
        from utils.json_request import enforce_json_request

        return enforce_json_request(
            request, enforce_ct=ENFORCE_JSON_CT, max_body=MAX_JSON_BODY
        )
