from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
ALLOW_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "allow_domains.txt"

def add_allow_domain_service(domain: str) -> None:
    domain = domain.strip()

    if not domain:
        raise ValueError("Domain cannot be empty")

    domains = set(
        line.strip()
        for line in ALLOW_DOMAIN_FILE.read_text().splitlines()
        if line.strip()
    )

    if domain in domains:
        raise ValueError("Domain already exists")

    domains.add(domain)
    ALLOW_DOMAIN_FILE.write_text("\n".join(sorted(domains)) + "\n")
