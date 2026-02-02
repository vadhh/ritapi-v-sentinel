from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_ASN_FILE = BASE_DIR / "config" / "feeds" / "deny_asn.txt"

def is_valid_asn(asn: str) -> bool:
    """Validate ASN format (AS followed by 1-10 digits)"""
    pattern = r'^AS\d{1,10}$'
    return bool(re.match(pattern, asn.upper()))

def add_deny_asn_service(asn: str) -> None:
    asn = asn.strip().upper()

    if not asn:
        raise ValueError("ASN cannot be empty")
    
    if not is_valid_asn(asn):
        raise ValueError("Invalid ASN format. Use format: AS12345")

    # Read existing ASNs (excluding comments)
    asns = set(
        line.strip()
        for line in DENY_ASN_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if asn in asns:
        raise ValueError("ASN already exists")

    asns.add(asn)
    
    # Write with header comment
    content = "# one ASN per line like AS12345\n" + "\n".join(sorted(asns)) + "\n"
    DENY_ASN_FILE.write_text(content)