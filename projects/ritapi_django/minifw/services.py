"""
Service layer untuk operasi MiniFW-AI
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class MiniFWConfig:
    """Handler untuk policy.json configuration"""
    
    POLICY_PATH = "/opt/minifw_ai/config/policy.json"
    
    @classmethod
    def load_policy(cls) -> Dict:
        """Load policy configuration"""
        try:
            with open(cls.POLICY_PATH, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    @classmethod
    def save_policy(cls, policy: Dict) -> bool:
        """Save policy configuration"""
        try:
            # Backup existing policy
            if os.path.exists(cls.POLICY_PATH):
                backup_path = f"{cls.POLICY_PATH}.backup"
                with open(cls.POLICY_PATH, 'r') as f:
                    with open(backup_path, 'w') as bf:
                        bf.write(f.read())
            
            # Write new policy
            with open(cls.POLICY_PATH, 'w') as f:
                json.dump(policy, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving policy: {e}")
            return False
    
    @classmethod
    def get_segments(cls) -> Dict:
        """Get segment configuration"""
        policy = cls.load_policy()
        return policy.get('segments', {})
    
    @classmethod
    def get_segment_subnets(cls) -> Dict:
        """Get segment subnet mappings"""
        policy = cls.load_policy()
        return policy.get('segment_subnets', {})
    
    @classmethod
    def update_segments(cls, segments: Dict) -> bool:
        """Update segment thresholds"""
        policy = cls.load_policy()
        policy['segments'] = segments
        return cls.save_policy(policy)
    
    @classmethod
    def update_segment_subnets(cls, subnets: Dict) -> bool:
        """Update segment subnet mappings"""
        policy = cls.load_policy()
        policy['segment_subnets'] = subnets
        return cls.save_policy(policy)
    
    @classmethod
    def get_features(cls) -> Dict:
        """Get feature weights"""
        policy = cls.load_policy()
        return policy.get('features', {})
    
    @classmethod
    def update_features(cls, features: Dict) -> bool:
        """Update feature weights"""
        policy = cls.load_policy()
        policy['features'] = features
        return cls.save_policy(policy)
    
    @classmethod
    def get_enforcement(cls) -> Dict:
        """Get enforcement configuration"""
        policy = cls.load_policy()
        return policy.get('enforcement', {})
    
    @classmethod
    def get_burst(cls) -> Dict:
        """Get burst configuration"""
        policy = cls.load_policy()
        return policy.get('burst', {})


class MiniFWFeeds:
    """Handler untuk feed files (allow/deny lists)"""
    
    FEEDS_DIR = "/opt/minifw_ai/config/feeds"
    
    FEED_FILES = {
        'allow_domains': 'allow_domains.txt',
        'deny_domains': 'deny_domains.txt',
        'deny_ips': 'deny_ips.txt',
        'deny_asn': 'deny_asn.txt',
    }
    
    @classmethod
    def read_feed(cls, feed_name: str) -> List[str]:
        """Read feed file and return list of entries"""
        file_path = os.path.join(cls.FEEDS_DIR, cls.FEED_FILES.get(feed_name, ''))
        
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Filter out comments and empty lines
            entries = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    entries.append(line)
            
            return entries
        except Exception as e:
            print(f"Error reading feed {feed_name}: {e}")
            return []
    
    @classmethod
    def write_feed(cls, feed_name: str, entries: List[str]) -> bool:
        """Write entries to feed file"""
        file_path = os.path.join(cls.FEEDS_DIR, cls.FEED_FILES.get(feed_name, ''))
        
        try:
            # Backup existing file
            if os.path.exists(file_path):
                backup_path = f"{file_path}.backup"
                with open(file_path, 'r') as f:
                    with open(backup_path, 'w') as bf:
                        bf.write(f.read())
            
            # Write new entries
            with open(file_path, 'w') as f:
                f.write("# Updated via RITAPI Dashboard\n")
                f.write(f"# Total entries: {len(entries)}\n\n")
                for entry in entries:
                    if entry.strip():
                        f.write(f"{entry.strip()}\n")
            
            return True
        except Exception as e:
            print(f"Error writing feed {feed_name}: {e}")
            return False
    
    @classmethod
    def add_to_feed(cls, feed_name: str, entry: str) -> bool:
        """Add single entry to feed"""
        entries = cls.read_feed(feed_name)
        if entry not in entries:
            entries.append(entry)
            return cls.write_feed(feed_name, entries)
        return True
    
    @classmethod
    def remove_from_feed(cls, feed_name: str, entry: str) -> bool:
        """Remove single entry from feed"""
        entries = cls.read_feed(feed_name)
        if entry in entries:
            entries.remove(entry)
            return cls.write_feed(feed_name, entries)
        return True


class MiniFWService:
    """Handler untuk MiniFW-AI service operations"""
    
    SERVICE_NAME = "minifw-ai"
    
    @classmethod
    def get_status(cls) -> Dict:
        """Get service status"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', cls.SERVICE_NAME],
                capture_output=True,
                text=True
            )
            is_active = result.stdout.strip() == 'active'
            
            result = subprocess.run(
                ['systemctl', 'is-enabled', cls.SERVICE_NAME],
                capture_output=True,
                text=True
            )
            is_enabled = result.stdout.strip() == 'enabled'
            
            return {
                'active': is_active,
                'enabled': is_enabled,
                'status': 'running' if is_active else 'stopped'
            }
        except Exception as e:
            return {
                'active': False,
                'enabled': False,
                'status': 'unknown',
                'error': str(e)
            }
    
    @classmethod
    def restart(cls) -> bool:
        """Restart MiniFW-AI service"""
        try:
            subprocess.run(['systemctl', 'restart', cls.SERVICE_NAME], check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    @classmethod
    def stop(cls) -> bool:
        """Stop MiniFW-AI service"""
        try:
            subprocess.run(['systemctl', 'stop', cls.SERVICE_NAME], check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    @classmethod
    def start(cls) -> bool:
        """Start MiniFW-AI service"""
        try:
            subprocess.run(['systemctl', 'start', cls.SERVICE_NAME], check=True)
            return True
        except subprocess.CalledProcessError:
            return False


class MiniFWIPSet:
    """Handler untuk ipset operations"""
    
    IPSET_NAME = "minifw_block_v4"
    
    @classmethod
    def list_blocked_ips(cls) -> List[str]:
        """List all blocked IPs from ipset"""
        try:
            result = subprocess.run(
                ['ipset', 'list', cls.IPSET_NAME],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse ipset output
            ips = []
            in_members = False
            for line in result.stdout.split('\n'):
                if line.startswith('Members:'):
                    in_members = True
                    continue
                if in_members and line.strip():
                    # Format: IP timeout VALUE
                    parts = line.strip().split()
                    if parts:
                        ips.append(parts[0])
            
            return ips
        except subprocess.CalledProcessError:
            return []
    
    @classmethod
    def add_ip(cls, ip: str, timeout: int = 86400) -> bool:
        """Add IP to block list"""
        try:
            subprocess.run(
                ['ipset', 'add', cls.IPSET_NAME, ip, 'timeout', str(timeout)],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    @classmethod
    def remove_ip(cls, ip: str) -> bool:
        """Remove IP from block list"""
        try:
            subprocess.run(
                ['ipset', 'del', cls.IPSET_NAME, ip],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    @classmethod
    def flush_all(cls) -> bool:
        """Flush all blocked IPs"""
        try:
            subprocess.run(
                ['ipset', 'flush', cls.IPSET_NAME],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False


class MiniFWStats:
    """Handler untuk statistics dan monitoring"""
    
    EVENTS_LOG = "/opt/minifw_ai/logs/events.jsonl"
    
    @classmethod
    def get_recent_events(cls, limit: int = 100) -> List[Dict]:
        """Get recent events from JSONL log"""
        if not os.path.exists(cls.EVENTS_LOG):
            return []
        
        events = []
        try:
            with open(cls.EVENTS_LOG, 'r') as f:
                # Read last N lines
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        event = json.loads(line.strip())
                        events.append(event)
                    except json.JSONDecodeError:
                        continue
            
            return events
        except Exception as e:
            print(f"Error reading events: {e}")
            return []
    
    @classmethod
    def get_stats(cls) -> Dict:
        """Get statistics from events"""
        events = cls.get_recent_events(1000)
        
        stats = {
            'total_events': len(events),
            'blocked': 0,
            'monitored': 0,
            'allowed': 0,
            'top_blocked_ips': {},
            'top_blocked_domains': {},
            'by_segment': {}
        }
        
        for event in events:
            action = event.get('action', 'unknown')
            if action == 'block':
                stats['blocked'] += 1
            elif action == 'monitor':
                stats['monitored'] += 1
            elif action == 'allow':
                stats['allowed'] += 1
            
            # Count by IP
            ip = event.get('client_ip', 'unknown')
            if action == 'block':
                stats['top_blocked_ips'][ip] = stats['top_blocked_ips'].get(ip, 0) + 1
            
            # Count by domain
            domain = event.get('domain', 'unknown')
            if action == 'block':
                stats['top_blocked_domains'][domain] = stats['top_blocked_domains'].get(domain, 0) + 1
            
            # Count by segment
            segment = event.get('segment', 'unknown')
            if segment not in stats['by_segment']:
                stats['by_segment'][segment] = {'blocked': 0, 'monitored': 0, 'allowed': 0}
            stats['by_segment'][segment][action] = stats['by_segment'][segment].get(action, 0) + 1
        
        # Sort top IPs and domains
        stats['top_blocked_ips'] = dict(sorted(stats['top_blocked_ips'].items(), key=lambda x: x[1], reverse=True)[:10])
        stats['top_blocked_domains'] = dict(sorted(stats['top_blocked_domains'].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return stats
