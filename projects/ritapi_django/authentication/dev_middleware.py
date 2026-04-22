from django.contrib.auth import get_user_model
from django.conf import settings

class DevAutoLoginMiddleware:
    """
    Automatically logs in the first superuser found in the database.
    ONLY active if settings.DEBUG is True.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only attempt auto-login if DEBUG is True and user isn't already logged in
        if getattr(settings, "DEBUG", False) and not request.user.is_authenticated:
            User = get_user_model()
            try:
                admin_user = User.objects.filter(is_superuser=True).first()
                if admin_user:
                    # In Django middleware, we can just set request.user.
                    # This bypasses the session requirement for that specific request.
                    request.user = admin_user
            except Exception:
                # Fail silently if DB isn't ready or User model is missing
                pass
                
        return self.get_response(request)
