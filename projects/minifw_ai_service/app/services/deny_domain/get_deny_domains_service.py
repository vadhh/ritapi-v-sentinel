from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "deny_domains.txt"


def get_deny_domains():
    if not DENY_DOMAIN_FILE.exists():
        return []

    with open(DENY_DOMAIN_FILE, "r") as f:
        domains = [
            {"name": line.strip()}
            for line in f.readlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    return domains