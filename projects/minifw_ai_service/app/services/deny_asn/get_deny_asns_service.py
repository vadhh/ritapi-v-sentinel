from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DENY_ASN_FILE = BASE_DIR / "config" / "feeds" / "deny_asn.txt"


def get_deny_asns():
    if not DENY_ASN_FILE.exists():
        return []

    with open(DENY_ASN_FILE, "r") as f:
        asns = [
            {"asn": line.strip()}
            for line in f.readlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    return asns