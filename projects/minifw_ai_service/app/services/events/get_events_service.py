from pathlib import Path
from datetime import datetime
import json

BASE_DIR = Path(__file__).resolve().parents[3]
EVENTS_FILE = BASE_DIR / "logs" / "events.jsonl"


def get_recent_events(limit: int = 100):
    """
    Get recent security events from JSONL file
    Returns list of recent events from log file
    """
    if not EVENTS_FILE.exists():
        # Return sample data if file doesn't exist
        return _get_sample_events()
    
    try:
        events = []
        
        # Read JSONL file (each line is a JSON object)
        with open(EVENTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    formatted_event = _format_event(event)
                    events.append(formatted_event)
                except json.JSONDecodeError:
                    continue
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda x: x.get('time', ''), reverse=True)
        
        # Return limited events
        return events[:limit]
    
    except (IOError, Exception) as e:
        print(f"Error reading events file: {e}")
        return _get_sample_events()


def _format_event(event: dict) -> dict:
    """
    Format event from JSONL to display format
    
    Log format:
    {
        "ts": "2025-12-17T06:32:51.298337+00:00",
        "segment": "default",
        "client_ip": "127.0.0.1",
        "domain": "chatgpt.com",
        "action": "allow",
        "score": 0,
        "reasons": []
    }
    
    Args:
        event: Raw event dict from JSONL
        
    Returns:
        Formatted event dict for DataTable
    """
    # Parse timestamp
    timestamp = event.get('ts', '')
    try:
        # Parse ISO format timestamp
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        time_str = timestamp
    
    # Get action (allow/block/deny)
    action = event.get('action', 'unknown')
    
    # Determine event type based on action and reasons
    reasons = event.get('reasons', [])
    event_type = _determine_event_type(action, reasons, event)
    
    # Get color based on action
    type_color = _get_action_color(action)
    
    # Get source (domain or IP)
    domain = event.get('domain', '')
    client_ip = event.get('client_ip', '')
    source = f"{domain} ({client_ip})" if domain else client_ip
    
    # Get status
    status = 'allowed' if action == 'allow' else 'blocked'
    
    # Check if threat detected
    score = event.get('score', 0)
    threat_detected = (score > 0) or (action != 'allow') or (len(reasons) > 0)
    
    # Format reasons
    reason_text = ', '.join(reasons) if reasons else 'Normal traffic'
    
    return {
        'time': time_str,
        'type': event_type,
        'type_color': type_color,
        'source': source,
        'status': status,
        'threat_detected': threat_detected,
        'reason': reason_text,
        'score': score,
        'segment': event.get('segment', 'default'),
        'client_ip': client_ip,
        'domain': domain
    }


def _determine_event_type(action: str, reasons: list, event: dict) -> str:
    """
    Determine event type based on action and reasons
    """
    # If has reasons, it's a specific block
    if reasons:
        if 'ip' in str(reasons).lower():
            return 'IP Block'
        elif 'domain' in str(reasons).lower():
            return 'Domain Block'
        elif 'asn' in str(reasons).lower():
            return 'ASN Block'
        elif 'burst' in str(reasons).lower() or 'rate' in str(reasons).lower():
            return 'Rate Limit'
        else:
            return 'Security Block'
    
    # Based on action
    if action == 'allow':
        domain = event.get('domain', '')
        if domain:
            return 'Domain Allow'
        else:
            return 'Traffic Allow'
    elif action in ['block', 'deny']:
        return 'Traffic Block'
    else:
        return 'Unknown'


def _get_action_color(action: str) -> str:
    """
    Get Bootstrap color class based on action
    """
    color_map = {
        'allow': 'success',
        'block': 'danger',
        'deny': 'danger',
        'warn': 'warning',
    }
    return color_map.get(action.lower(), 'secondary')


def _get_sample_events():
    """
    Return sample events if file doesn't exist
    """
    return [
        {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'Domain Allow',
            'type_color': 'success',
            'source': 'chatgpt.com (127.0.0.1)',
            'status': 'allowed',
            'threat_detected': False,
            'reason': 'Normal traffic',
            'score': 0,
            'segment': 'default',
            'client_ip': '127.0.0.1',
            'domain': 'chatgpt.com'
        },
        {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'Domain Allow',
            'type_color': 'success',
            'source': 'connectivity-check.ubuntu.com (127.0.0.1)',
            'status': 'allowed',
            'threat_detected': False,
            'reason': 'Normal traffic',
            'score': 0,
            'segment': 'default',
            'client_ip': '127.0.0.1',
            'domain': 'connectivity-check.ubuntu.com'
        }
    ]


def get_event_statistics():
    """
    Get event statistics
    Returns counts of allowed, blocked, threats
    """
    events = get_recent_events(limit=10000)
    
    stats = {
        'total_allowed': 0,
        'total_blocked': 0,
        'threats_detected': 0
    }
    
    for event in events:
        if event.get('status') == 'allowed':
            stats['total_allowed'] += 1
        elif event.get('status') == 'blocked':
            stats['total_blocked'] += 1
        
        if event.get('threat_detected', False):
            stats['threats_detected'] += 1
    
    return stats


def get_system_uptime():
    """
    Calculate system uptime
    Returns uptime percentage
    """
    # TODO: Implement real uptime calculation
    return "99.8%"