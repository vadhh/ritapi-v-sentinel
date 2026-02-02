from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_IP_FILE = BASE_DIR / "config" / "feeds" / "deny_ips.txt"

def delete_deny_ip_service(ip: str) -> None:
    ip = ip.strip()

    if not ip:
        raise ValueError("IP address cannot be empty")

    # Read existing IPs (excluding comments)
    ips = set(
        line.strip()
        for line in DENY_IP_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if ip not in ips:
        raise ValueError("IP address not found")

    ips.remove(ip)
    
    # Write with header comment
    content = "# one IPv4 per line\n" + "\n".join(sorted(ips)) + "\n"
    DENY_IP_FILE.write_text(content)