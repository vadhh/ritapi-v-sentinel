from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class OpsAuthMiddleware:
    """
    Middleware to protect all /ops/ routes.
    Deny-by-default: users must be authenticated and have an active UserProfile
    (or be a superuser) to access /ops/ pages. Locked accounts are denied.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/ops/'):
            if request.path.startswith('/login') or request.path.startswith('/logout'):
                return self.get_response(request)

            if not request.user.is_authenticated:
                messages.warning(request, 'Please login to access the dashboard.')
                return redirect(f"{reverse('login')}?next={request.path}")

            # Deny-by-default: must pass an explicit allow condition
            profile = getattr(request.user, 'profile', None)
            if profile is None:
                try:
                    from minifw.models import UserProfile
                    profile = UserProfile.objects.get(user=request.user)
                except Exception:
                    pass

            allowed = False

            if request.user.is_superuser:
                allowed = True
            elif profile is not None:
                if profile.is_locked:
                    messages.error(request, 'Your account is locked. Contact an administrator.')
                else:
                    allowed = True

            if not allowed:
                if not messages.get_messages(request):
                    messages.error(request, 'You do not have permission to access this area.')
                return redirect('login')

        return self.get_response(request)
