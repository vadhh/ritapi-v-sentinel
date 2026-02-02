from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_ASN_FILE = BASE_DIR / "config" / "feeds" / "deny_asn.txt"

def delete_deny_asn_service(asn: str) -> None:
    asn = asn.strip().upper()

    if not asn:
        raise ValueError("ASN cannot be empty")

    # Read existing ASNs (excluding comments)
    asns = set(
        line.strip()
        for line in DENY_ASN_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    if asn not in asns:
        raise ValueError("ASN not found")

    asns.remove(asn)
    
    # Write with header comment
    content = "# one ASN per line like AS12345\n" + "\n".join(sorted(asns)) + "\n"
    DENY_ASN_FILE.write_text(content)