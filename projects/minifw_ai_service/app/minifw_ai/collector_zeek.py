from __future__ import annotations
import time
from pathlib import Path
from typing import Iterator, Optional, Tuple

def tail_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            yield line.rstrip("\n")

def parse_zeek_ssl_tsv(line: str) -> Optional[Tuple[str, str]]:
    if not line or line.startswith("#"):
        return None
    parts = line.split("\t")
    try:
        client_ip = parts[2]
        sni = ""
        for p in parts:
            if "." in p and any(c.isalpha() for c in p) and 3 <= len(p) <= 253:
                sni = p
                break
        if client_ip and sni:
            return client_ip, sni
    except Exception:
        return None
    return None

def stream_zeek_sni_events(log_path: str):
    p = Path(log_path)
    if not p.exists():
        raise FileNotFoundError(f"Missing Zeek ssl.log: {p}")
    for ln in tail_lines(p):
        evt = parse_zeek_ssl_tsv(ln)
        if evt:
            yield evt
