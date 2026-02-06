"""
Views untuk MiniFW-AI Configuration
4 Menu Utama:
1. Dashboard & Statistics
2. Policy Configuration (Segments & Thresholds)
3. Feed Management (Allow/Deny Lists)
4. Blocked IPs Management
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .services import (
    MiniFWConfig,
    MiniFWFeeds,
    MiniFWService,
    MiniFWIPSet,
    MiniFWStats,
    SectorLock,
    AuditService
)


# ============================================
# 1. Dashboard & Statistics
# ============================================

def minifw_dashboard(request):
    """MiniFW-AI Dashboard dengan statistics"""
    context = {
        'service_status': MiniFWService.get_status(),
        'stats': MiniFWStats.get_stats(),
        'recent_events': MiniFWStats.get_recent_events(50),
        'blocked_ips_count': len(MiniFWIPSet.list_blocked_ips()),
        'sector': SectorLock.get_sector(),
        'sector_desc': SectorLock.get_description(),
    }
    return render(request, 'ops_template/minifw_config/dashboard.html', context)


# ============================================
# 2. Policy Configuration
# ============================================

def minifw_policy(request):
    """
    Policy Configuration Page
    - Segments & Thresholds
    - Segment Subnets
    - Feature Weights
    - Burst Configuration
    """
    if request.method == 'POST':
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
    policy = MiniFWConfig.load_policy()
    
    context = {
        'segments': MiniFWConfig.get_segments(),
        'segment_subnets': MiniFWConfig.get_segment_subnets(),
        'features': MiniFWConfig.get_features(),
        'burst': MiniFWConfig.get_burst(),
        'enforcement': MiniFWConfig.get_enforcement(),
        'service_status': MiniFWService.get_status(),
    }
    
    return render(request, 'ops_template/minifw_config/policy.html', context)


# ============================================
# 3. Feed Management
# ============================================

def minifw_feeds(request):
    """
    Feed Management Page
    - Allow Domains
    - Deny Domains
    - Deny IPs
    - Deny ASNs
    """
    if request.method == 'POST':
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
    context = {
        'allow_domains': MiniFWFeeds.read_feed('allow_domains'),
        'deny_domains': MiniFWFeeds.read_feed('deny_domains'),
        'deny_ips': MiniFWFeeds.read_feed('deny_ips'),
        'deny_asn': MiniFWFeeds.read_feed('deny_asn'),
        'service_status': MiniFWService.get_status(),
    }
    
    return render(request, 'ops_template/minifw_config/feeds.html', context)


# ============================================
# 4. Blocked IPs Management
# ============================================

def minifw_blocked_ips(request):
    """
    Blocked IPs Management Page
    - View currently blocked IPs
    - Manually block/unblock IPs
    - View block history
    """
    if request.method == 'POST':
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
    context = {
        'blocked_ips': MiniFWIPSet.list_blocked_ips(),
        'recent_blocks': [
            event for event in MiniFWStats.get_recent_events(100)
            if event.get('action') == 'block'
        ],
        'service_status': MiniFWService.get_status(),
    }
    
    return render(request, 'ops_template/minifw_config/blocked_ips.html', context)


# ============================================
# 5. Audit Logs (Stub)
# ============================================

@login_required
@require_http_methods(["GET"])
def minifw_audit_logs(request):
    """
    Stub for displaying system audit logs to prevent crash.
    """
    context = {
        'logs': [],
        'service_status': MiniFWService.get_status(),
    }
    return render(request, 'ops_template/minifw_config/audit_logs.html', context)


# ============================================
# Service Control Actions
# ============================================

@require_http_methods(["POST"])
def minifw_service_control(request):
    """Control MiniFW-AI service"""
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

def minifw_api_stats(request):
    """API endpoint untuk real-time stats"""
    return JsonResponse(MiniFWStats.get_stats())


def minifw_api_service_status(request):
    """API endpoint untuk service status"""
    return JsonResponse(MiniFWService.get_status())


def minifw_api_recent_events(request):
    """API endpoint untuk recent events"""
    limit = int(request.GET.get('limit', 50))
    events = MiniFWStats.get_recent_events(limit)
    return JsonResponse({'events': events})
