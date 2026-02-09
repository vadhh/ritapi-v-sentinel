from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class OpsAuthMiddleware:
    """
    Middleware to protect all /ops/ routes.
    RBAC-aware: users with a UserProfile can access based on role.
    Backward compatible: superusers without a profile are still allowed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/ops/'):
            if not request.path.startswith('/login') and not request.path.startswith('/logout'):
                if not request.user.is_authenticated:
                    messages.warning(request, 'Please login to access the dashboard.')
                    return redirect(f"{reverse('login')}?next={request.path}")

                # RBAC check: profile exists → allow any role to access /ops/
                profile = getattr(request.user, 'profile', None)
                if profile is None:
                    try:
                        from minifw.models import UserProfile
                        profile = UserProfile.objects.get(user=request.user)
                    except Exception:
                        pass

                if profile is not None:
                    # User has a profile — allowed to access /ops/
                    pass
                elif request.user.is_superuser:
                    # Backward compat: superuser without profile (pre-migration)
                    pass
                else:
                    messages.error(request, 'You do not have permission to access this area.')
                    return redirect('login')

        response = self.get_response(request)
        return response
