from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_DOMAIN_FILE = BASE_DIR / "config" / "feeds" / "deny_domains.txt"

def update_deny_domain_service(old_domain: str, new_domain: str) -> None:
    old_domain = old_domain.strip().lower()
    new_domain = new_domain.strip().lower()

    if not new_domain:
        raise ValueError("New domain cannot be empty")

    # Read existing domains (excluding comments)
    domains = set(
        line.strip()
        for line in DENY_DOMAIN_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if old_domain not in domains:
        raise ValueError("Original domain not found")

    if new_domain in domains and new_domain != old_domain:
        raise ValueError("New domain already exists")

    domains.remove(old_domain)
    domains.add(new_domain)
    
    # Preserve comment if exists
    original_content = DENY_DOMAIN_FILE.read_text()
    has_comment = any(line.startswith("#") for line in original_content.splitlines())
    if has_comment:
        comment_lines = [line for line in original_content.splitlines() if line.startswith("#")]
        content = "\n".join(comment_lines) + "\n" + "\n".join(sorted(domains)) + "\n"
    else:
        content = "\n".join(sorted(domains)) + "\n"
    
    DENY_DOMAIN_FILE.write_text(content)