from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class OpsAuthMiddleware:
    """
    Middleware to protect all /ops/ routes
    Only superusers can access ops routes
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if the request is for an ops route
        if request.path.startswith('/ops/'):
            # Exclude login and logout URLs
            if not request.path.startswith('/login') and not request.path.startswith('/logout'):
                # Check if user is authenticated and is superuser
                if not request.user.is_authenticated:
                    messages.warning(request, 'Please login to access the dashboard.')
                    return redirect(f"{reverse('login')}?next={request.path}")
                
                if not request.user.is_superuser:
                    messages.error(request, 'You must be a superuser to access this area.')
                    return redirect('login')
        
        response = self.get_response(request)
        return response