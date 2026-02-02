from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
ALLOW_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "allow_domains.txt"

def update_allow_domain_service(old_domain: str, new_domain: str) -> None:
    domains = [
        line.strip()
        for line in ALLOW_DOMAIN_FILE.read_text().splitlines()
        if line.strip()
    ]

    if old_domain not in domains:
        raise ValueError("Domain not found")

    if new_domain in domains:
        raise ValueError("New domain already exists")

    updated = [
        new_domain if d == old_domain else d
        for d in domains
    ]

    ALLOW_DOMAIN_FILE.write_text("\n".join(updated) + "\n")
