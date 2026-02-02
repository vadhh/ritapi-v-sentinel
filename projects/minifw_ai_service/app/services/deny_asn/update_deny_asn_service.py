from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_ASN_FILE = BASE_DIR / "config" / "feeds" / "deny_asn.txt"

def is_valid_asn(asn: str) -> bool:
    """Validate ASN format (AS followed by 1-10 digits)"""
    pattern = r'^AS\d{1,10}$'
    return bool(re.match(pattern, asn.upper()))

def update_deny_asn_service(old_asn: str, new_asn: str) -> None:
    old_asn = old_asn.strip().upper()
    new_asn = new_asn.strip().upper()

    if not new_asn:
        raise ValueError("New ASN cannot be empty")
    
    if not is_valid_asn(new_asn):
        raise ValueError("Invalid ASN format. Use format: AS12345")

    # Read existing ASNs (excluding comments)
    asns = set(
        line.strip()
        for line in DENY_ASN_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if old_asn not in asns:
        raise ValueError("Original ASN not found")

    if new_asn in asns and new_asn != old_asn:
        raise ValueError("New ASN already exists")

    asns.remove(old_asn)
    asns.add(new_asn)
    
    # Write with header comment
    content = "# one ASN per line like AS12345\n" + "\n".join(sorted(asns)) + "\n"
    DENY_ASN_FILE.write_text(content)