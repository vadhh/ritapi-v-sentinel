#!/usr/bin/env python3
import os
import sys
import django
import random
from datetime import timedelta
from django.utils import timezone

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.join(BASE_DIR, "projects", "ritapi_django")
sys.path.append(PROJECT_ROOT)

# Set environment variables for Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ritapi_v_sentinel.settings")
os.environ["DJANGO_SECRET_KEY"] = "demo-secret-key-12345"
os.environ["DJANGO_DEBUG"] = "True"

# FORCE SQLITE for demo
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(PROJECT_ROOT, 'demo_db.sqlite3')}"

# Mock production paths to current directory
MOCK_BASE = os.path.join(BASE_DIR, "demo_data")
os.makedirs(MOCK_BASE, exist_ok=True)
os.makedirs(os.path.join(MOCK_BASE, "logs"), exist_ok=True)
os.makedirs(os.path.join(MOCK_BASE, "config", "feeds"), exist_ok=True)
os.makedirs(os.path.join(MOCK_BASE, "var_log"), exist_ok=True)

os.environ["MINIFW_POLICY_PATH"] = os.path.join(MOCK_BASE, "config", "policy.json")
os.environ["MINIFW_LOG"] = os.path.join(MOCK_BASE, "logs", "events.jsonl")
os.environ["MINIFW_SECTOR_LOCK"] = os.path.join(MOCK_BASE, "config", "sector_lock.json")
os.environ["MINIFW_DEPLOYMENT_STATE"] = os.path.join(MOCK_BASE, "var_log", "deployment_state.json")

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

def clear_data():
    print("Clearing existing data...")
    UserProfile.objects.all().delete()
    User.objects.all().delete()
    Alert.objects.all().delete()
    BlockedIP.objects.all().delete()
    RequestLog.objects.all().delete()
    MiniFWEvent.objects.all().delete()
    MiniFWBlockedIP.objects.all().delete()
    AuditLog.objects.all().delete()
    AsnInfo.objects.all().delete()
    AsnTrustConfig.objects.all().delete()
    IpReputation.objects.all().delete()
    InternalIPList.objects.all().delete()
    JsonSchema.objects.all().delete()

def create_superusers():
    print("Creating superusers...")
    admin, created = User.objects.get_or_create(username='admin')
    if created:
        admin.set_password('admin123')
        admin.email = 'admin@example.com'
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
    
    UserProfile.objects.update_or_create(
        user=admin, 
        defaults={'role': 'SUPER_ADMIN', 'sector': 'GOVERNMENT', 'full_name': 'Global Administrator'}
    )
    
    operator, created = User.objects.get_or_create(username='operator')
    if created:
        operator.set_password('operator123')
        operator.email = 'operator@example.com'
        operator.is_staff = True
        operator.is_superuser = True # Ops dashboard requires superuser in views.py
        operator.save()
    
    UserProfile.objects.update_or_create(
        user=operator, 
        defaults={'role': 'OPERATOR', 'sector': 'HOSPITAL', 'full_name': 'System Operator'}
    )
    
    print(f"  - Created/Updated admin:admin123")
    print(f"  - Created/Updated operator:operator123")

def seed_alerts():
    print("Seeding alerts...")
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
    print("Seeding request logs...")
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
    print("Seeding blocked IPs...")
    ips = ['45.33.22.11', '185.22.33.44', '99.88.77.66', '123.123.123.123']
    for ip in ips:
        BlockedIP.objects.create(
            ip_address=ip,
            reason="Repeated login failures and port scanning detected.",
            severity=random.choice(['high', 'critical']),
            country="RU",
            country_name="Russian Federation",
            active=True
        )

def seed_minifw_events():
    print("Seeding MiniFW events...")
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

def seed_asn_and_iprep():
    print("Seeding ASN and IP Reputation...")
    AsnTrustConfig.objects.update_or_create(asn_number="AS15169", defaults={'name': "Google LLC", 'score': 95.0})
    AsnTrustConfig.objects.update_or_create(asn_number="AS16509", defaults={'name': "Amazon.com, Inc.", 'score': 90.0})
    AsnTrustConfig.objects.update_or_create(asn_number="AS13335", defaults={'name': "Cloudflare, Inc.", 'score': 85.0})
    
    AsnInfo.objects.create(ip_address="8.8.8.8", asn_number="AS15169", trust_score=95.0, asn_description="Google DNS")
    
    IpReputation.objects.create(
        ip_address="45.33.22.11",
        reputation_score=15.0,
        scores={"spam": 80, "malware": 40, "bot": 60},
        isp="Linode",
        country="US"
    )

def seed_json_schemas():
    print("Seeding JSON Schemas...")
    JsonSchema.objects.create(
        name="User Profile Update",
        endpoint="/api/v1/user",
        method="POST",
        schema_json={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "email": {"type": "string", "format": "email"}
            },
            "required": ["username"]
        },
        rollout_mode="enforce"
    )

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RITAPI Demo Seeder")
    parser.add_argument("--reset", action="store_true", help="Clear all demo data and exit")
    args = parser.parse_args()

    print(f"Demo Tool started for Project: {PROJECT_ROOT}")
    
    # Run migrations first
    print("Ensuring database schema is up to date...")
    from django.core.management import execute_from_command_line
    # We need to use execute_from_command_line to properly run migrations
    # Mocking sys.argv for migrate
    old_argv = sys.argv
    sys.argv = ['manage.py', 'migrate']
    try:
        execute_from_command_line(sys.argv)
    except Exception as e:
        print(f"Migration error: {e}")
    sys.argv = old_argv

    clear_data()
    if args.reset:
        print("\n" + "="*50)
        print("DATABASE RESET SUCCESSFULLY")
        print("="*50)
        return

    create_superusers()
    seed_alerts()
    seed_request_logs()
    seed_blocked_ips()
    seed_minifw_events()
    seed_asn_and_iprep()
    seed_json_schemas()
    
    print("\n" + "="*50)
    print("DEMO DATA SEEDED SUCCESSFULLY")
    print("="*50)
    print(f"Database: {os.path.join(PROJECT_ROOT, 'demo_db.sqlite3')}")
    print("\nYou can now run the development server:")
    print(f"cd projects/ritapi_django")
    print(f"export DJANGO_SECRET_KEY=demo-secret-key-12345")
    print(f"export DATABASE_URL=sqlite:///demo_db.sqlite3")
    print(f"./venv/bin/python manage.py runserver")
    print("="*50)

if __name__ == "__main__":
    main()
