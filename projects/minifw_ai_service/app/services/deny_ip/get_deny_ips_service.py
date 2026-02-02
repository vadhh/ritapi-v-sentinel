from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_IP_FILE = BASE_DIR / "config" / "feeds" / "deny_ips.txt"


def get_deny_ips():
    if not DENY_IP_FILE.exists():
        return []

    with open(DENY_IP_FILE, "r") as f:
        ips = [
            {"ip": line.strip()}
            for line in f.readlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    return ips