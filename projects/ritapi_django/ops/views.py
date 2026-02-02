from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test


def is_superuser(user):
    """Check if user is authenticated and is superuser"""
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_superuser, login_url='login')
def dashboard(request):
    """
    Main ops dashboard - only accessible to superusers
    """
    from alert.models import Alert
    from blocking.models import BlockedIP
    from log_channel.models import RequestLog
    
    # Get statistics
    total_alerts = Alert.objects.count()
    total_blocked = BlockedIP.objects.filter(active=True).count()
    
    # Use 'action' instead of 'decision'
    total_requests_allow = RequestLog.objects.filter(action='ALLOW').count()
    total_requests_block = RequestLog.objects.filter(action='BLOCK').count()
    
    # Get recent data
    recent_alerts = Alert.objects.order_by('-timestamp')[:5]
    
    context = {
        'total_alerts': total_alerts,
        'total_blocked': total_blocked,
        'total_requests_allow': total_requests_allow,
        'total_requests_block': total_requests_block,
        'recent_alerts': recent_alerts,
    }
    
    return render(request, 'ops_template/dashboard.html', context)