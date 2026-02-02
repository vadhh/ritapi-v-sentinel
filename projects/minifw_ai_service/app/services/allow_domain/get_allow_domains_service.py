from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
ALLOW_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "allow_domains.txt"


def get_allow_domains():
    if not ALLOW_DOMAIN_FILE.exists():
        return []

    with open(ALLOW_DOMAIN_FILE, "r") as f:
        domains = [
            {"name": line.strip()}
            for line in f.readlines()
            if line.strip()
        ]

    return domains
