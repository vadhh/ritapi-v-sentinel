"""
Views untuk MiniFW-AI Configuration
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .services import (
    MiniFWConfig,
    MiniFWFeeds,
    MiniFWService,
    MiniFWIPSet,
    MiniFWStats,
    MiniFWEventsService,
    SectorLock,
    AuditService,
    RBACService,
    UserManagementService,
)


def _require_permission(request, check_fn, error_msg, redirect_url='minifw_dashboard'):
    """Check RBAC permission for HTML form views. Returns redirect if denied, None if allowed."""
    if not check_fn(request.user):
        messages.error(request, error_msg)
        return redirect(redirect_url)
    return None


# ============================================
# 1. Dashboard & Statistics
# ============================================

@login_required
def minifw_dashboard(request):
    """MiniFW-AI Dashboard dengan statistics"""
    try:
        service_status = MiniFWService.get_status()
    except Exception:
        service_status = {'active': False, 'enabled': False, 'status': 'unknown'}

    try:
        stats = MiniFWStats.get_stats()
    except Exception:
        stats = {
            'total_events': 0, 'blocked': 0, 'monitored': 0, 'allowed': 0,
            'top_blocked_ips': {}, 'top_blocked_domains': {}, 'by_segment': {},
        }

    try:
        recent_events = MiniFWStats.get_recent_events(50)
    except Exception:
        recent_events = []

    try:
        blocked_ips_count = len(MiniFWIPSet.list_blocked_ips())
    except Exception:
        blocked_ips_count = 0

    context = {
        'service_status': service_status,
        'stats': stats,
        'recent_events': recent_events,
        'blocked_ips_count': blocked_ips_count,
        'sector': SectorLock.get_sector(),
        'sector_desc': SectorLock.get_description(),
    }
    return render(request, 'ops_template/minifw_config/dashboard.html', context)


# ============================================
# 2. Policy Configuration
# ============================================

@login_required
def minifw_policy(request):
    """
    Policy Configuration Page
    - Segments & Thresholds
    - Segment Subnets
    - Feature Weights
    - Burst Configuration
    """
    if request.method == 'POST':
        denied = _require_permission(request, RBACService.can_modify_policy,
            'Permission denied. Admin role required to modify policy.', 'minifw_policy')
        if denied:
            return denied

        action = request.POST.get('action')

        if action == 'update_segments':
            # Update segment thresholds
            segments = {}
            for key in request.POST:
                if key.startswith('segment_'):
                    parts = key.split('_')
                    if len(parts) >= 3:
                        segment_name = parts[1]
                        field = parts[2]

                        if segment_name not in segments:
                            segments[segment_name] = {}

                        segments[segment_name][field] = int(request.POST[key])

            if MiniFWConfig.update_segments(segments):
                AuditService.log_action(request, 'policy_updated', f'Updated segment thresholds: {list(segments.keys())}', severity='warning', resource_type='policy')
                messages.success(request, 'Segment thresholds updated successfully')
            else:
                messages.error(request, 'Failed to update segment thresholds')

        elif action == 'update_subnets':
            # Update segment subnets
            subnets = {}
            for key in request.POST:
                if key.startswith('subnet_'):
                    segment_name = key.replace('subnet_', '')
                    subnet_list = request.POST[key].strip().split('\n')
                    subnet_list = [s.strip() for s in subnet_list if s.strip()]
                    subnets[segment_name] = subnet_list

            if MiniFWConfig.update_segment_subnets(subnets):
                AuditService.log_action(request, 'policy_updated', f'Updated segment subnets mapping', severity='warning', resource_type='policy')
                messages.success(request, 'Segment subnets updated successfully')
                # Restart service to apply changes
                MiniFWService.restart()
            else:
                messages.error(request, 'Failed to update segment subnets')

        elif action == 'update_features':
            # Update feature weights
            features = {
                'dns_weight': int(request.POST.get('dns_weight', 40)),
                'sni_weight': int(request.POST.get('sni_weight', 35)),
                'asn_weight': int(request.POST.get('asn_weight', 15)),
                'burst_weight': int(request.POST.get('burst_weight', 10)),
            }

            if MiniFWConfig.update_features(features):
                AuditService.log_action(request, 'policy_updated', f'Updated feature weights', severity='warning', resource_type='policy')
                messages.success(request, 'Feature weights updated successfully')
                MiniFWService.restart()
            else:
                messages.error(request, 'Failed to update feature weights')

        return redirect('minifw_policy')

    # GET request
    try:
        policy = MiniFWConfig.load_policy()
        context = {
            'segments': MiniFWConfig.get_segments(),
            'segment_subnets': MiniFWConfig.get_segment_subnets(),
            'features': MiniFWConfig.get_features(),
            'burst': MiniFWConfig.get_burst(),
            'enforcement': MiniFWConfig.get_enforcement(),
            'service_status': MiniFWService.get_status(),
        }
    except Exception:
        context = {
            'segments': {}, 'segment_subnets': {}, 'features': {},
            'burst': {}, 'enforcement': {},
            'service_status': {'active': False, 'enabled': False, 'status': 'unknown'},
        }

    return render(request, 'ops_template/minifw_config/policy.html', context)


# ============================================
# 3. Feed Management
# ============================================

@login_required
def minifw_feeds(request):
    """
    Feed Management Page
    - Allow Domains
    - Deny Domains
    - Deny IPs
    - Deny ASNs
    """
    if request.method == 'POST':
        denied = _require_permission(request, RBACService.can_modify_policy,
            'Permission denied. Admin role required to modify feeds.', 'minifw_feeds')
        if denied:
            return denied

        action = request.POST.get('action')
        feed_name = request.POST.get('feed_name')

        if action == 'update_feed':
            # Update entire feed
            entries_text = request.POST.get('entries', '')
            entries = [line.strip() for line in entries_text.split('\n') if line.strip()]

            if MiniFWFeeds.write_feed(feed_name, entries):
                AuditService.log_action(request, 'feed_updated', f'Updated feed: {feed_name}', severity='warning', resource_type='feed')
                messages.success(request, f'{feed_name} updated successfully')
                # Restart service to reload feeds
                MiniFWService.restart()
            else:
                messages.error(request, f'Failed to update {feed_name}')

        elif action == 'add_entry':
            # Add single entry
            entry = request.POST.get('entry', '').strip()
            if entry:
                if MiniFWFeeds.add_to_feed(feed_name, entry):
                    AuditService.log_action(request, 'feed_updated', f'Added entry to {feed_name}: {entry}', severity='info', resource_type='feed')
                    messages.success(request, f'Added {entry} to {feed_name}')
                    MiniFWService.restart()
                else:
                    messages.error(request, f'Failed to add entry')

        elif action == 'remove_entry':
            # Remove single entry
            entry = request.POST.get('entry', '').strip()
            if entry:
                if MiniFWFeeds.remove_from_feed(feed_name, entry):
                    AuditService.log_action(request, 'feed_updated', f'Removed entry from {feed_name}: {entry}', severity='info', resource_type='feed')
                    messages.success(request, f'Removed {entry} from {feed_name}')
                    MiniFWService.restart()
                else:
                    messages.error(request, f'Failed to remove entry')

        return redirect('minifw_feeds')

    # GET request
    try:
        context = {
            'allow_domains': MiniFWFeeds.read_feed('allow_domains'),
            'deny_domains': MiniFWFeeds.read_feed('deny_domains'),
            'deny_ips': MiniFWFeeds.read_feed('deny_ips'),
            'deny_asn': MiniFWFeeds.read_feed('deny_asn'),
            'service_status': MiniFWService.get_status(),
        }
    except Exception:
        context = {
            'allow_domains': [], 'deny_domains': [], 'deny_ips': [], 'deny_asn': [],
            'service_status': {'active': False, 'enabled': False, 'status': 'unknown'},
        }

    return render(request, 'ops_template/minifw_config/feeds.html', context)


# ============================================
# 4. Blocked IPs Management
# ============================================

@login_required
def minifw_blocked_ips(request):
    """
    Blocked IPs Management Page
    - View currently blocked IPs
    - Manually block/unblock IPs
    - View block history
    """
    if request.method == 'POST':
        denied = _require_permission(request, RBACService.can_execute_enforcement,
            'Permission denied. Operator role required for IP enforcement.', 'minifw_blocked_ips')
        if denied:
            return denied

        action = request.POST.get('action')

        if action == 'block_ip':
            # Manually block an IP
            ip = request.POST.get('ip', '').strip()
            timeout = int(request.POST.get('timeout', 86400))

            if ip:
                if MiniFWIPSet.add_ip(ip, timeout):
                    messages.success(request, f'Blocked {ip} for {timeout} seconds')
                else:
                    messages.error(request, f'Failed to block {ip}')

        elif action == 'unblock_ip':
            # Unblock an IP
            ip = request.POST.get('ip', '').strip()

            if ip:
                if MiniFWIPSet.remove_ip(ip):
                    messages.success(request, f'Unblocked {ip}')
                else:
                    messages.error(request, f'Failed to unblock {ip}')

        elif action == 'flush_all':
            # Flush all blocked IPs
            if MiniFWIPSet.flush_all():
                messages.success(request, 'All blocked IPs cleared')
            else:
                messages.error(request, 'Failed to clear blocked IPs')

        return redirect('minifw_blocked_ips')

    # GET request
    try:
        blocked_ips = MiniFWIPSet.list_blocked_ips()
    except Exception:
        blocked_ips = []

    try:
        recent_blocks = [
            event for event in MiniFWStats.get_recent_events(100)
            if event.get('action') == 'block'
        ]
    except Exception:
        recent_blocks = []

    try:
        service_status = MiniFWService.get_status()
    except Exception:
        service_status = {'active': False, 'enabled': False, 'status': 'unknown'}

    context = {
        'blocked_ips': blocked_ips,
        'recent_blocks': recent_blocks,
        'service_status': service_status,
    }

    return render(request, 'ops_template/minifw_config/blocked_ips.html', context)


# ============================================
# 5. Audit Logs
# ============================================

@login_required
@require_http_methods(["GET"])
def minifw_audit_logs(request):
    """Full audit logs page with filters."""
    context = {
        'service_status': MiniFWService.get_status(),
    }
    return render(request, 'ops_template/minifw_config/audit_logs.html', context)


# ============================================
# 6. Events
# ============================================

@login_required
@require_http_methods(["GET"])
def minifw_events(request):
    """Events page with DataTables."""
    return render(request, 'ops_template/minifw_config/events.html', {
        'service_status': MiniFWService.get_status(),
    })


# ============================================
# 7. User Management
# ============================================

@login_required
def minifw_users(request):
    """User management page (SUPER_ADMIN only)."""
    if not RBACService.check_permission(request.user, 'SUPER_ADMIN'):
        messages.error(request, 'Access denied. Super Admin role required.')
        return redirect('minifw_dashboard')
    return render(request, 'ops_template/minifw_config/user_management.html', {
        'service_status': MiniFWService.get_status(),
    })


# ============================================
# Service Control Actions
# ============================================

@login_required
@require_http_methods(["POST"])
def minifw_service_control(request):
    """Control MiniFW-AI service"""
    denied = _require_permission(request, RBACService.can_execute_enforcement,
        'Permission denied. Operator role required for service control.', 'minifw_dashboard')
    if denied:
        return denied

    action = request.POST.get('action')

    if action == 'restart':
        if MiniFWService.restart():
            messages.success(request, 'MiniFW-AI service restarted successfully')
        else:
            messages.error(request, 'Failed to restart MiniFW-AI service')

    elif action == 'stop':
        if MiniFWService.stop():
            messages.success(request, 'MiniFW-AI service stopped')
        else:
            messages.error(request, 'Failed to stop MiniFW-AI service')

    elif action == 'start':
        if MiniFWService.start():
            messages.success(request, 'MiniFW-AI service started')
        else:
            messages.error(request, 'Failed to start MiniFW-AI service')

    # Redirect to referer or dashboard
    referer = request.META.get('HTTP_REFERER', 'minifw_dashboard')
    return redirect(referer)


# ============================================
# API Endpoints (AJAX)
# ============================================

@login_required
def minifw_api_stats(request):
    """API endpoint untuk real-time stats"""
    try:
        return JsonResponse(MiniFWStats.get_stats())
    except Exception:
        return JsonResponse({
            'total_events': 0, 'blocked': 0, 'monitored': 0, 'allowed': 0,
            'top_blocked_ips': {}, 'top_blocked_domains': {}, 'by_segment': {},
        })


@login_required
def minifw_api_service_status(request):
    """API endpoint untuk service status"""
    try:
        return JsonResponse(MiniFWService.get_status())
    except Exception:
        return JsonResponse({'active': False, 'enabled': False, 'status': 'unknown'})


@login_required
def minifw_api_recent_events(request):
    """API endpoint untuk recent events"""
    try:
        limit = int(request.GET.get('limit', 50))
        events = MiniFWStats.get_recent_events(limit)
        return JsonResponse({'events': events})
    except Exception:
        return JsonResponse({'events': []})


# ============================================
# Events API
# ============================================

@login_required
@require_http_methods(["GET"])
def minifw_api_events_datatable(request):
    """DataTables server-side processing for events."""
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search = request.GET.get('search[value]', '')
    order_col = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'desc')

    result = MiniFWEventsService.get_events_datatable(
        draw=draw, start=start, length=length,
        search=search, order_col=order_col, order_dir=order_dir,
    )
    return JsonResponse(result)


@login_required
@require_http_methods(["GET"])
def minifw_api_events_export(request):
    """Export events to Excel."""
    if not RBACService.can_export_data(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    action_filter = request.GET.get('action_filter', 'all')
    buf = MiniFWEventsService.export_events_excel(action_filter)
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="minifw_events.xlsx"'
    return response


# ============================================
# Audit Logs API
# ============================================

@login_required
@require_http_methods(["GET"])
def minifw_api_audit_logs(request):
    """Paginated audit logs as JSON."""
    if not RBACService.can_access_audit(request.user):
        return JsonResponse({'error': 'Permission denied. Auditor role required.'}, status=403)

    limit = min(int(request.GET.get('limit', 50)), 200)
    offset = int(request.GET.get('offset', 0))
    filters = {}
    for key in ('action', 'severity', 'username', 'resource_type', 'start_date', 'end_date'):
        val = request.GET.get(key)
        if val:
            filters[key] = val
    data = AuditService.get_logs(limit=limit, offset=offset, filters=filters)
    return JsonResponse(data)


@login_required
@require_http_methods(["GET"])
def minifw_api_audit_statistics(request):
    """Audit log severity counts."""
    if not RBACService.can_access_audit(request.user):
        return JsonResponse({'error': 'Permission denied. Auditor role required.'}, status=403)

    days = int(request.GET.get('days', 7))
    return JsonResponse(AuditService.get_statistics(days=days))


@login_required
@require_http_methods(["GET"])
def minifw_api_audit_export(request):
    """Export audit logs as JSON file."""
    if not RBACService.can_export_data(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    content = AuditService.export_logs(start_date=start_date, end_date=end_date)
    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.json"'
    return response


# ============================================
# User Management API
# ============================================

def _require_super_admin(user):
    if not RBACService.check_permission(user, 'SUPER_ADMIN'):
        return JsonResponse({'error': 'Super Admin role required'}, status=403)
    return None


@login_required
@require_http_methods(["GET"])
def minifw_api_users_list(request):
    """List all users with profiles."""
    denied = _require_super_admin(request.user)
    if denied:
        return denied

    from .models import UserProfile
    users = []
    for u in User.objects.all().select_related('profile').order_by('id'):
        profile = getattr(u, 'profile', None)
        users.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'is_active': u.is_active,
            'is_superuser': u.is_superuser,
            'date_joined': u.date_joined.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'role': profile.role if profile else ('SUPER_ADMIN' if u.is_superuser else 'VIEWER'),
            'sector': profile.sector if profile else 'ESTABLISHMENT',
            'full_name': profile.full_name if profile else '',
            'department': profile.department if profile else '',
            'phone': profile.phone if profile else '',
            'is_locked': profile.is_locked if profile else False,
        })
    return JsonResponse({'users': users})


@login_required
@csrf_protect
@require_http_methods(["POST"])
def minifw_api_users_create(request):
    """Create a new user."""
    denied = _require_super_admin(request.user)
    if denied:
        return denied

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    required = ('username', 'password', 'role')
    for field in required:
        if not data.get(field):
            return JsonResponse({'error': f'Missing required field: {field}'}, status=400)

    if User.objects.filter(username=data['username']).exists():
        return JsonResponse({'error': 'Username already exists'}, status=400)

    try:
        user, profile = UserManagementService.create_user(
            username=data['username'],
            email=data.get('email', ''),
            password=data['password'],
            role=data['role'],
            sector=data.get('sector', 'ESTABLISHMENT'),
            created_by=request.user.id,
            request=request,
            full_name=data.get('full_name', ''),
            department=data.get('department', ''),
            phone=data.get('phone', ''),
        )
        return JsonResponse({'id': user.id, 'username': user.username})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_protect
@require_http_methods(["PUT"])
def minifw_api_users_update(request, user_id):
    """Update user profile."""
    denied = _require_super_admin(request.user)
    if denied:
        return denied

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    try:
        user, profile = UserManagementService.update_user(
            user_id=user_id,
            updated_by=request.user.id,
            request=request,
            **{k: v for k, v in data.items()
               if k in ('email', 'role', 'sector', 'full_name', 'department', 'phone')},
        )
        return JsonResponse({'id': user.id, 'username': user.username})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_protect
@require_http_methods(["PUT"])
def minifw_api_users_password(request, user_id):
    """Change user password."""
    denied = _require_super_admin(request.user)
    if denied:
        return denied

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    password = data.get('password', '')
    if len(password) < 8:
        return JsonResponse({'error': 'Password must be at least 8 characters'}, status=400)

    try:
        UserManagementService.change_password(
            user_id=user_id,
            new_password=password,
            changed_by=request.user.id,
            request=request,
        )
        return JsonResponse({'success': True})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_protect
@require_http_methods(["DELETE"])
def minifw_api_users_delete(request, user_id):
    """Delete a user."""
    denied = _require_super_admin(request.user)
    if denied:
        return denied

    try:
        UserManagementService.delete_user(
            user_id=user_id,
            deleted_by=request.user.id,
            request=request,
        )
        return JsonResponse({'success': True})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def minifw_api_current_user(request):
    """Return current user info + role."""
    user = request.user
    role = RBACService.get_user_role(user)
    profile = getattr(user, 'profile', None)
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': role,
        'sector': profile.sector if profile else 'ESTABLISHMENT',
        'full_name': profile.full_name if profile else '',
        'permissions': {
            'can_modify_policy': RBACService.can_modify_policy(user),
            'can_execute_enforcement': RBACService.can_execute_enforcement(user),
            'can_access_audit': RBACService.can_access_audit(user),
            'can_export_data': RBACService.can_export_data(user),
        },
    })


@login_required
@require_http_methods(["GET"])
def minifw_api_sector_lock(request):
    """Return sector lock configuration (read-only)."""
    return JsonResponse(SectorLock.get_full_config())
