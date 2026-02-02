from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_IP_FILE = BASE_DIR / "config" / "feeds" / "deny_ips.txt"

def is_valid_ipv4(ip: str) -> bool:
    """Validate IPv4 address format"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    
    parts = ip.split('.')
    return all(0 <= int(part) <= 255 for part in parts)

def update_deny_ip_service(old_ip: str, new_ip: str) -> None:
    old_ip = old_ip.strip()
    new_ip = new_ip.strip()

    if not new_ip:
        raise ValueError("New IP address cannot be empty")
    
    if not is_valid_ipv4(new_ip):
        raise ValueError("Invalid IPv4 address format")

    # Read existing IPs (excluding comments)
    ips = set(
        line.strip()
        for line in DENY_IP_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if old_ip not in ips:
        raise ValueError("Original IP address not found")

    if new_ip in ips and new_ip != old_ip:
        raise ValueError("New IP address already exists")

    ips.remove(old_ip)
    ips.add(new_ip)
    
    # Write with header comment
    content = "# one IPv4 per line\n" + "\n".join(sorted(ips)) + "\n"
    DENY_IP_FILE.write_text(content)