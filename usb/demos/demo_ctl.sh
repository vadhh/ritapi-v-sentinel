#!/usr/bin/env bash
# USB-specific demo controller — uses docker exec, no venv needed.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

CONTAINER="vsentinel-django"

die() { echo "ERROR: $*" >&2; exit 1; }

docker inspect "$CONTAINER" >/dev/null 2>&1 || die "Container '$CONTAINER' is not running. Run ./demo.sh first."

SEED_SCRIPT='
import random
from datetime import timedelta
from django.utils import timezone
from alert.models import Alert
from blocking.models import BlockedIP
from log_channel.models import RequestLog
from minifw.models import MiniFWEvent, MiniFWBlockedIP, AuditLog
from asn.models import AsnInfo, AsnTrustConfig
from ip_reputation.models import IpReputation

def seed():
    now = timezone.now()

    # Clear existing demo data
    Alert.objects.all().delete()
    RequestLog.objects.all().delete()
    MiniFWEvent.objects.all().delete()
    MiniFWBlockedIP.objects.all().delete()
    BlockedIP.objects.all().delete()
    AuditLog.objects.all().delete()
    AsnInfo.objects.all().delete()
    AsnTrustConfig.objects.all().delete()
    IpReputation.objects.all().delete()

    # ------------------------------------------------------------------ #
    # Seed Alerts (20)
    # ------------------------------------------------------------------ #
    alert_types = [
        "brute_force", "sql_injection", "xss_attempt", "port_scan",
        "dos_attempt", "credential_stuffing", "path_traversal",
        "suspicious_user_agent", "rate_limit_exceeded", "tor_exit_node",
    ]
    severities = ["low", "medium", "high", "critical"]
    attacker_ips = [
        "185.220.101.12", "45.33.32.156", "198.51.100.7", "203.0.113.42",
        "91.108.4.18", "62.210.180.229", "194.165.16.33", "80.82.77.139",
        "171.25.193.20", "176.10.99.200",
    ]
    for i in range(20):
        Alert.objects.create(
            alert_type=alert_types[i % len(alert_types)],
            ip_address=attacker_ips[i % len(attacker_ips)],
            detail=f"Detected {alert_types[i % len(alert_types)].replace(\"_\", \" \")} from source. "
                   f"Request count: {random.randint(10, 500)}. Threshold exceeded.",
            severity=severities[i % len(severities)],
            resolved=(i % 5 == 0),
        )

    # ------------------------------------------------------------------ #
    # Seed RequestLogs (100)
    # ------------------------------------------------------------------ #
    paths = [
        "/api/v1/login", "/api/v1/patients", "/api/v1/records",
        "/admin/", "/api/v1/users", "/api/v1/export",
        "/api/v1/search", "/api/v1/upload", "/static/js/app.js",
        "/api/v1/status",
    ]
    methods = ["GET", "POST", "PUT", "DELETE"]
    actions = ["allow", "block", "monitor"]
    labels = [
        "clean_or_unknown", "sql_injection_possible", "xss_possible",
        "rate_limited", "brute_force_possible", "gambling_possible",
        "clean_or_unknown", "clean_or_unknown", "clean_or_unknown", "monitor_threshold",
    ]
    client_ips = [
        "10.0.0.101", "10.0.0.102", "192.168.1.50",
        "185.220.101.12", "45.33.32.156", "203.0.113.42",
        "172.16.0.5", "198.51.100.7", "10.0.0.200", "91.108.4.18",
    ]
    for i in range(100):
        idx = i % 10
        action = actions[0] if idx < 6 else (actions[1] if idx < 8 else actions[2])
        label = labels[idx]
        score = round(random.uniform(0.0, 0.3), 3) if action == "allow" else \
                round(random.uniform(0.6, 1.0), 3) if action == "block" else \
                round(random.uniform(0.3, 0.6), 3)
        RequestLog.objects.create(
            ip_address=client_ips[idx],
            path=paths[idx],
            method=methods[i % len(methods)],
            body_size=random.randint(0, 8192),
            score=score,
            label=label,
            action=action,
            reasons=f"Rule match: {label}. Score threshold: {score}. "
                    f"Evaluated at request #{i + 1}.",
        )

    # ------------------------------------------------------------------ #
    # Seed BlockedIPs (10)
    # ------------------------------------------------------------------ #
    blocked_data = [
        ("185.220.101.12", "Repeated brute-force login attempts", "high", "RU", "Russia", 55.7558, 37.6176),
        ("45.33.32.156",   "SQL injection payload detected",      "critical", "US", "United States", 37.3861, -122.0839),
        ("198.51.100.7",   "Port scan detected across services",  "medium", "DE", "Germany", 52.5200, 13.4050),
        ("203.0.113.42",   "DoS flood — request rate exceeded",   "high", "CN", "China", 39.9042, 116.4074),
        ("91.108.4.18",    "Known Tor exit node",                 "medium", "NL", "Netherlands", 52.3676, 4.9041),
        ("62.210.180.229", "Credential stuffing campaign",        "high", "FR", "France", 48.8566, 2.3522),
        ("194.165.16.33",  "Malware C2 callback detected",        "critical", "IR", "Iran", 35.6892, 51.3890),
        ("80.82.77.139",   "Scanner — CVE-2021-44228 probe",      "high", "NL", "Netherlands", 52.3676, 4.9041),
        ("171.25.193.20",  "Tor exit node — suspicious activity", "medium", "SE", "Sweden", 59.3293, 18.0686),
        ("176.10.99.200",  "Repeated path traversal attempts",    "medium", "NO", "Norway", 59.9139, 10.7522),
    ]
    for ip, reason, severity, country, country_name, lat, lon in blocked_data:
        BlockedIP.objects.create(
            ip_address=ip,
            reason=reason,
            severity=severity,
            country=country,
            country_name=country_name,
            latitude=lat,
            longitude=lon,
        )

    # ------------------------------------------------------------------ #
    # Seed MiniFWEvents (30)
    # ------------------------------------------------------------------ #
    segments = ["hospital", "finance", "government", "education", "legal"]
    domains = [
        "google.com", "github.com", "malware-host.ru", "torrentsite.bz",
        "suspicious-cdn.xyz", "update.microsoft.com", "api.stripe.com",
        "phishing-kit.top", "cloudflare.com", "casino-promo.bet",
    ]
    mfw_actions = ["allow", "monitor", "block"]
    for i in range(30):
        domain = domains[i % len(domains)]
        action = mfw_actions[0] if i % 3 == 0 else (mfw_actions[1] if i % 3 == 1 else mfw_actions[2])
        MiniFWEvent.objects.create(
            timestamp=now - timedelta(minutes=i * 3),
            segment=segments[i % len(segments)],
            client_ip=client_ips[i % len(client_ips)],
            domain=domain,
            action=action,
            score=random.randint(0, 100),
            reasons=["policy_block"] if action == "block" else ["reputation_check"],
        )

    # ------------------------------------------------------------------ #
    # Seed MiniFWBlockedIPs (5)
    # ------------------------------------------------------------------ #
    for i, (ip, reason, _, _, _, _, _) in enumerate(blocked_data[:5]):
        MiniFWBlockedIP.objects.get_or_create(
            ip_address=ip,
            defaults=dict(
                expires_at=now + timedelta(hours=24),
                segment=segments[i % len(segments)],
                reason=reason,
                score=random.randint(60, 100),
                auto_blocked=True,
            ),
        )

    # ------------------------------------------------------------------ #
    # Seed AuditLogs (10)
    # ------------------------------------------------------------------ #
    audit_actions = [
        "USER_LOGIN", "POLICY_UPDATE", "IP_BLOCKED", "IP_UNBLOCKED",
        "EXPORT_DATA", "USER_LOGOUT", "CONFIG_CHANGE", "ALERT_RESOLVED",
        "USER_LOGIN", "POLICY_UPDATE",
    ]
    audit_users = ["admin", "operator1", "auditor1", "admin", "operator2",
                   "admin", "operator1", "auditor1", "admin", "operator2"]
    for i in range(10):
        AuditLog.objects.create(
            username=audit_users[i],
            user_role="ADMIN" if "admin" in audit_users[i] else "OPERATOR",
            action=audit_actions[i],
            severity="info" if i % 3 != 2 else "warning",
            description=f"Action \"{audit_actions[i]}\" performed by {audit_users[i]}.",
            ip_address=client_ips[i % len(client_ips)],
            success=True,
        )

    # ------------------------------------------------------------------ #
    # Seed AsnInfo + AsnTrustConfig (5 each)
    # ------------------------------------------------------------------ #
    asn_data = [
        ("AS15169", "Google LLC",           9.2,  "10.0.0.101", "Google autonomous system — major cloud provider."),
        ("AS13335", "Cloudflare Inc.",       8.8,  "10.0.0.102", "Cloudflare CDN and DDoS protection network."),
        ("AS174",   "Cogent Communications", 6.5, "198.51.100.7", "Tier-1 transit provider with mixed reputation."),
        ("AS60068", "Datacamp Limited",      3.1,  "185.220.101.12", "Associated with VPN/proxy services."),
        ("AS396507","Tor Project",           1.0,  "171.25.193.20", "Tor exit node operator."),
    ]
    for asn_num, name, score, ip, desc in asn_data:
        AsnInfo.objects.create(
            ip_address=ip,
            asn_number=asn_num,
            trust_score=score,
            asn_description=desc,
            is_latest=True,
        )
        AsnTrustConfig.objects.get_or_create(
            asn_number=asn_num,
            defaults=dict(name=name, score=score),
        )

    # ------------------------------------------------------------------ #
    # Seed IpReputation (4)
    # ------------------------------------------------------------------ #
    ip_rep_data = [
        ("185.220.101.12", {"abuse": 0.95, "spam": 0.80, "botnet": 0.70}, 0.92),
        ("45.33.32.156",   {"abuse": 0.85, "spam": 0.60, "botnet": 0.50}, 0.78),
        ("10.0.0.101",     {"abuse": 0.02, "spam": 0.01, "botnet": 0.00}, 0.02),
        ("203.0.113.42",   {"abuse": 0.75, "spam": 0.55, "botnet": 0.65}, 0.70),
    ]
    for ip, scores_dict, rep_score in ip_rep_data:
        IpReputation.objects.get_or_create(
            ip_address=ip,
            defaults=dict(scores=scores_dict, reputation_score=rep_score),
        )

    print("Demo data seeded successfully.")

seed()
'

RESET_SCRIPT='
from alert.models import Alert
from blocking.models import BlockedIP
from log_channel.models import RequestLog
from minifw.models import MiniFWEvent, MiniFWBlockedIP, AuditLog
from asn.models import AsnInfo, AsnTrustConfig
from ip_reputation.models import IpReputation

Alert.objects.all().delete()
RequestLog.objects.all().delete()
MiniFWEvent.objects.all().delete()
MiniFWBlockedIP.objects.all().delete()
BlockedIP.objects.all().delete()
AuditLog.objects.all().delete()
AsnInfo.objects.all().delete()
AsnTrustConfig.objects.all().delete()
IpReputation.objects.all().delete()
print("Demo data cleared.")
'

case "${1:-}" in
    seed)
        echo -e "${BLUE}>>> Injecting V-Sentinel demo data...${NC}"
        docker exec "$CONTAINER" python manage.py shell -c "$SEED_SCRIPT"
        echo -e "${GREEN}>>> Done.${NC}"
        ;;
    reset)
        echo -e "${RED}>>> Removing V-Sentinel demo data...${NC}"
        docker exec "$CONTAINER" python manage.py shell -c "$RESET_SCRIPT"
        echo -e "${GREEN}>>> Done.${NC}"
        ;;
    *)
        echo "Usage: $0 {seed|reset}"
        echo "  seed  - Inject realistic sample data into existing database"
        echo "  reset - Wipe sample logs/alerts for a fresh start"
        exit 1
        ;;
esac
