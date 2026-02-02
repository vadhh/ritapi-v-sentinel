from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "deny_domains.txt"

def delete_deny_domain_service(domain: str) -> None:
    domain = domain.strip().lower()

    if not domain:
        raise ValueError("Domain cannot be empty")

    # Read existing domains (excluding comments)
    domains = set(
        line.strip()
        for line in DENY_DOMAIN_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if domain not in domains:
        raise ValueError("Domain not found")

    domains.remove(domain)
    
    # Preserve comment if exists
    original_content = DENY_DOMAIN_FILE.read_text()
    has_comment = any(line.startswith("#") for line in original_content.splitlines())
    if has_comment:
        comment_lines = [line for line in original_content.splitlines() if line.startswith("#")]
        content = "\n".join(comment_lines) + "\n" + "\n".join(sorted(domains)) + "\n"
    else:
        content = "\n".join(sorted(domains)) + "\n"
    
    DENY_DOMAIN_FILE.write_text(content)