#!/usr/bin/env python3
import os
import sys
import django
import random
import json
from datetime import timedelta
from django.utils import timezone

# --- CONFIGURATION & PATH DETECTION ---
# Try to detect if we are in production (/opt/ritapi_v_sentinel) or dev
PRODUCTION_ROOT = "/opt/ritapi_v_sentinel"
if os.path.exists(PRODUCTION_ROOT):
    PROJECT_ROOT = PRODUCTION_ROOT
    ENV_FILE = "/etc/ritapi/vsentinel.env"
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROJECT_ROOT = os.path.join(BASE_DIR, "projects", "ritapi_django")
    ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

sys.path.append(PROJECT_ROOT)

# --- ENVIRONMENT SETUP ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ritapi_v_sentinel.settings")

# Load environment variables if file exists
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")
                except ValueError:
                    continue

# Fallbacks for dev/local testing
if "DJANGO_SECRET_KEY" not in os.environ:
    os.environ["DJANGO_SECRET_KEY"] = "demo-secret-key-temporary"
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(PROJECT_ROOT, 'demo_db.sqlite3')}"

# Initialize Django
django.setup()

from django.contrib.auth.models import User
from alert.models import Alert
from blocking.models import BlockedIP
from log_channel.models import RequestLog
from minifw.models import UserProfile, MiniFWEvent, MiniFWBlockedIP, AuditLog
from asn.models import AsnInfo, AsnTrustConfig
from ip_reputation.models import IpReputation, InternalIPList
from json_schema.models import JsonSchema

def clear_demo_data():
    """Clears existing logs/alerts but keeps Users/Config intact if preferred, 
    but here we wipe to ensure fresh demo state."""
    print("Clearing existing monitoring data...")
    Alert.objects.all().delete()
    RequestLog.objects.all().delete()
    MiniFWEvent.objects.all().delete()
    # We keep MiniFWBlockedIP and BlockedIP to show 'active' blocks, 
    # but for a 'reset' we might want them gone.
    MiniFWBlockedIP.objects.all().delete()
    BlockedIP.objects.all().delete()
    AuditLog.objects.all().delete()

def seed_alerts():
    print("Injecting alerts...")
    severities = ['low', 'medium', 'high', 'critical']
    types = ['SQL Injection Attempt', 'Brute Force Attack', 'Malware Beacon', 'Unauthorized Access', 'DDoS Burst']
    ips = ['192.168.1.10', '45.33.22.11', '10.0.0.5', '185.22.33.44', '99.88.77.66']
    
    for _ in range(20):
        Alert.objects.create(
            alert_type=random.choice(types),
            ip_address=random.choice(ips),
            detail=f"Detected suspicious activity from {random.choice(ips)} targeting internal resources.",
            severity=random.choice(severities),
            resolved=random.choice([True, False])
        )

def seed_request_logs():
    print("Injecting request logs...")
    actions = ['ALLOW', 'BLOCK', 'MONITOR']
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    paths = ['/api/v1/user', '/login', '/api/v1/data', '/admin', '/static/js/app.js', '/.env', '/wp-admin']
    ips = ['192.168.1.100', '10.0.0.50', '172.16.0.5', '45.33.22.11', '185.22.33.44']
    
    now = timezone.now()
    for i in range(100):
        action = random.choice(actions)
        score = random.uniform(0.7, 1.0) if action == 'BLOCK' else random.uniform(0.0, 0.4)
        RequestLog.objects.create(
            ip_address=random.choice(ips),
            path=random.choice(paths),
            method=random.choice(methods),
            body_size=random.randint(0, 5000),
            score=score,
            label='clean' if action == 'ALLOW' else 'threat',
            action=action,
            reasons='Normal traffic' if action == 'ALLOW' else 'Pattern matched malicious signature',
            timestamp=now - timedelta(minutes=i*5)
        )

def seed_blocked_ips():
    print("Injecting blocked IPs with Geo-coordinates...")
    # IP, Reason, Country, Lat, Lon
    targets = [
        ('45.33.22.11', "SQL Injection", "US", 37.75, -122.41),
        ('185.22.33.44', "Brute Force", "RU", 55.75, 37.61),
        ('99.88.77.66', "Botnet Activity", "CN", 39.90, 116.40),
        ('123.123.123.123', "DDoS", "NL", 52.36, 4.89)
    ]
    for ip, reason, country, lat, lon in targets:
        BlockedIP.objects.update_or_create(
            ip_address=ip,
            defaults={
                'reason': reason,
                'severity': random.choice(['high', 'critical']),
                'country': country,
                'latitude': lat,
                'longitude': lon,
                'active': True
            }
        )

def seed_minifw_events():
    print("Injecting MiniFW security events...")
    domains = ['google.com', 'malware.xyz', 'casino-win.top', 'github.com', 'tor-proxy.net']
    ips = ['192.168.1.5', '192.168.1.6', '192.168.1.7']
    segments = ['Internal_LAN', 'Guest_WiFi', 'Server_Farm']
    
    now = timezone.now()
    for i in range(50):
        domain = random.choice(domains)
        action = 'block' if 'malware' in domain or 'casino' in domain or 'tor' in domain else 'allow'
        MiniFWEvent.objects.create(
            timestamp=now - timedelta(minutes=i*2),
            segment=random.choice(segments),
            client_ip=random.choice(ips),
            domain=domain,
            action=action,
            score=random.randint(70, 100) if action == 'block' else random.randint(0, 30),
            reasons=['dns_blocklist'] if action == 'block' else []
        )

def seed_config_data():
    """Injects auxiliary config data if tables are empty."""
    print("Ensuring auxiliary config data (ASN/Reputation/Schema)...")
    if not AsnTrustConfig.objects.exists():
        AsnTrustConfig.objects.create(asn_number="AS15169", name="Google LLC", score=95.0)
        AsnTrustConfig.objects.create(asn_number="AS16509", name="Amazon.com, Inc.", score=90.0)
    
    if not JsonSchema.objects.exists():
        JsonSchema.objects.create(
            name="API User Validation", endpoint="/api/v1/user", method="POST",
            schema_json={"type": "object", "properties": {"username": {"type": "string"}}},
            rollout_mode="enforce"
        )

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RITAPI Demo Injector")
    parser.add_argument("--reset", action="store_true", help="Clear injected demo data")
    args = parser.parse_args()

    print(f"RITAPI Demo Tool | Context: {PROJECT_ROOT}")
    
    clear_demo_data()
    
    if args.reset:
        print("\n" + "="*50)
        print("DEMO DATA REMOVED SUCCESSFULLY")
        print("="*50)
        return

    seed_alerts()
    seed_request_logs()
    seed_blocked_ips()
    seed_minifw_events()
    seed_config_data()
    
    print("\n" + "="*50)
    print("DEMO DATA INJECTED SUCCESSFULLY")
    print("="*50)
    print("Dashboard: http://157.66.9.210/ops/")
    print("="*50)

if __name__ == "__main__":
    main()
