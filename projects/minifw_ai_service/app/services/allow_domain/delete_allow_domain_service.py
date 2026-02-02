from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
ALLOW_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "allow_domains.txt"

def delete_allow_domain_service(domain: str) -> None:
    domains = [
        line.strip()
        for line in ALLOW_DOMAIN_FILE.read_text().splitlines()
        if line.strip()
    ]

    if domain not in domains:
        raise ValueError("Domain not found")

    domains.remove(domain)
    ALLOW_DOMAIN_FILE.write_text("\n".join(domains) + "\n")
