#!/usr/bin/env python3
"""
demos/demo_dns_flood.py — V-Sentinel DNS Query Flood Generator

Sends DNS queries at a controlled rate to trigger MiniFW-AI burst detection
and/or DNS denied-domain scoring. Uses only Python stdlib (socket module).

Usage:
    python3 demos/demo_dns_flood.py                        # default: burst flood
    python3 demos/demo_dns_flood.py --mode denied          # denied domains only
    python3 demos/demo_dns_flood.py --mode burst           # random subdomains, high rate
    python3 demos/demo_dns_flood.py --mode combined        # denied + burst together
    python3 demos/demo_dns_flood.py --rate 300 --duration 60
    python3 demos/demo_dns_flood.py --server 10.0.0.1 --port 53

Scoring reference (from policy.json):
    dns_weight = 41  (single denied domain hit)
    burst_weight = 10  (added when >240 queries/min from one IP)
    default block_threshold = 60
    → denied + burst = 51 → MONITOR
    → With demo policy (threshold=35): → BLOCK
"""

import argparse
import random
import socket
import struct
import sys
import time
from typing import Iterator

# ---------------------------------------------------------------------------
# Denied domain patterns (must match deny_domains.txt in config/feeds/)
# These match: *.slot*, *.casino*, *malware*, *.judionline*
DENIED_DOMAINS = [
    "slots.example.com",
    "casino-demo.example.com",
    "slotgames.example.com",
    "malware-test.example.com",
    "judionline-demo.example.com",
    "best-slots.example.com",
    "casino777.example.com",
    "slots-free.example.com",
]

# Benign-looking domains for burst (high volume, not denied — tests rate detection)
BENIGN_DOMAINS = [
    "api.example.com",
    "cdn.example.com",
    "updates.example.com",
    "telemetry.example.com",
    "metrics.example.com",
    "health.example.com",
    "sync.example.com",
    "data.example.com",
]

# ---------------------------------------------------------------------------

def build_dns_query(domain: str, qtype: int = 1) -> bytes:
    """
    Build a minimal DNS query packet for the given domain.

    Args:
        domain: FQDN to query
        qtype:  DNS record type (1=A, 28=AAAA, 15=MX)

    Returns:
        Raw DNS query bytes ready to send over UDP
    """
    txid = random.randint(0, 0xFFFF)
    flags = 0x0100  # Standard query, recursion desired
    qdcount = 1
    header = struct.pack(">HHHHHH", txid, flags, qdcount, 0, 0, 0)

    # Encode domain as DNS labels
    labels = b""
    for part in domain.rstrip(".").split("."):
        encoded = part.encode("ascii")
        labels += struct.pack("B", len(encoded)) + encoded
    labels += b"\x00"  # root label

    question = labels + struct.pack(">HH", qtype, 1)  # qtype, qclass=IN
    return header + question


def send_query(sock: socket.socket, server: str, port: int, domain: str) -> bool:
    """
    Send one DNS query. Returns True on success, False on error.
    Errors are silently swallowed — the domain won't resolve, which is expected.
    """
    try:
        pkt = build_dns_query(domain)
        sock.sendto(pkt, (server, port))
        return True
    except OSError:
        return False


def domain_generator(mode: str) -> Iterator[str]:
    """Yield domains to query based on mode."""
    if mode == "denied":
        while True:
            yield random.choice(DENIED_DOMAINS)
    elif mode == "burst":
        counter = 0
        while True:
            # Mix benign with occasional denied to show combined scoring
            if counter % 20 == 0:
                yield random.choice(DENIED_DOMAINS)
            else:
                # Random subdomains to avoid DNS caching skewing counts
                subdomain = f"node{random.randint(1000, 9999)}.example.com"
                yield subdomain
            counter += 1
    elif mode == "combined":
        # Alternating: denied domain, then burst, then denied, etc.
        counter = 0
        while True:
            if counter % 3 == 0:
                yield random.choice(DENIED_DOMAINS)
            else:
                yield random.choice(BENIGN_DOMAINS + [
                    f"sub{random.randint(100, 999)}.example.com"
                ])
            counter += 1
    else:
        raise ValueError(f"Unknown mode: {mode}")


def run_flood(
    server: str,
    port: int,
    mode: str,
    rate: int,
    duration: int,
    verbose: bool,
) -> None:
    """
    Main flood loop.

    Args:
        server:   DNS server IP
        port:     DNS port (usually 53)
        mode:     'denied', 'burst', or 'combined'
        rate:     Target queries per minute
        duration: How long to run in seconds
        verbose:  Print each query if True
    """
    interval = 60.0 / rate  # seconds between each query

    print(f"\n[V-Sentinel DNS Flood]")
    print(f"  Server:    {server}:{port}")
    print(f"  Mode:      {mode}")
    print(f"  Rate:      {rate} queries/min  (interval: {interval:.3f}s)")
    print(f"  Duration:  {duration}s")
    print(f"  MiniFW burst block threshold: 240/min (burst_weight=+10)")
    print(f"  Press Ctrl-C to stop early\n")

    # Scoring context
    if mode in ("denied", "combined"):
        print(f"  [Scoring] dns_denied_domain: +41pts per denied query")
        print(f"            burst_behavior:    +10pts when rate >240/min")
        print(f"            default threshold: 60 (MONITOR=40)")
        print(f"            demo threshold:    35 (if --setup-demo-policy applied)\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)

    gen = domain_generator(mode)
    sent = 0
    errors = 0
    denied_count = 0
    start = time.monotonic()
    deadline = start + duration
    last_report = start

    try:
        while time.monotonic() < deadline:
            loop_start = time.monotonic()

            domain = next(gen)
            is_denied = any(
                pat.replace("*", "") in domain
                for pat in ["slot", "casino", "malware", "judionline"]
            )
            if is_denied:
                denied_count += 1

            ok = send_query(sock, server, port, domain)
            if ok:
                sent += 1
            else:
                errors += 1

            if verbose or (is_denied and mode != "burst"):
                tag = " [DENIED]" if is_denied else ""
                print(f"  {sent:5d}  →  {domain}{tag}")

            # Progress report every 10 seconds
            now = time.monotonic()
            if now - last_report >= 10:
                elapsed = now - start
                actual_rate = int(sent * 60 / elapsed) if elapsed > 0 else 0
                remaining = int(deadline - now)
                print(
                    f"  [Progress] sent={sent} | denied={denied_count} | "
                    f"rate=~{actual_rate}/min | remaining={remaining}s"
                )
                last_report = now

            # Pace to target rate
            elapsed_loop = time.monotonic() - loop_start
            sleep_time = interval - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n  [Interrupted by user]")
    finally:
        sock.close()

    total_time = time.monotonic() - start
    actual_rate = int(sent * 60 / total_time) if total_time > 0 else 0

    print(f"\n[Summary]")
    print(f"  Queries sent:     {sent}")
    print(f"  Denied domains:   {denied_count}")
    print(f"  Errors:           {errors}")
    print(f"  Duration:         {total_time:.1f}s")
    print(f"  Actual rate:      ~{actual_rate}/min")
    print(f"  Burst threshold:  240/min → {'EXCEEDED' if actual_rate >= 240 else 'not reached'}")

    if actual_rate >= 240:
        print(f"\n  Expected MiniFW scoring:")
        if mode in ("denied", "combined"):
            print(f"    dns_denied_domain: +41 pts")
            print(f"    burst_behavior:    +10 pts")
            print(f"    total:             51 pts → MONITOR (default) / BLOCK (demo policy)")
        else:
            print(f"    burst_behavior: +10 pts → added to any other active signals")
    else:
        print(f"\n  Rate did not exceed burst threshold (240/min).")
        print(f"  Try: python3 demos/demo_dns_flood.py --rate 300 --duration 30")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V-Sentinel DNS query flood for demo purposes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  denied    Query domains from the deny list (slots, casino, malware, judionline)
            → Triggers dns_denied_domain scoring (+41 pts per event)

  burst     High-rate queries (mostly benign domains)
            → Triggers burst_behavior (+10 pts) when rate >240/min

  combined  Denied domains at burst rate (default)
            → Triggers both: dns_denied_domain + burst_behavior (51 pts)

Examples:
  python3 demos/demo_dns_flood.py                          # combined, 300/min, 60s
  python3 demos/demo_dns_flood.py --mode denied --rate 60  # slow denied queries
  python3 demos/demo_dns_flood.py --mode burst --rate 400  # burst only
  python3 demos/demo_dns_flood.py --server 10.0.0.1        # external DNS
  python3 demos/demo_dns_flood.py --verbose                # print every query
""",
    )
    parser.add_argument(
        "--server", default="127.0.0.1",
        help="DNS server IP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=53,
        help="DNS port (default: 53)"
    )
    parser.add_argument(
        "--mode", choices=["denied", "burst", "combined"], default="combined",
        help="Query mode (default: combined)"
    )
    parser.add_argument(
        "--rate", type=int, default=300,
        help="Target queries per minute (default: 300, burst threshold: 240)"
    )
    parser.add_argument(
        "--duration", type=int, default=60,
        help="Duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print every query (slow — use for denied mode demos)"
    )

    args = parser.parse_args()

    if args.rate < 1:
        print("ERROR: --rate must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.duration < 1:
        print("ERROR: --duration must be >= 1", file=sys.stderr)
        sys.exit(1)

    run_flood(
        server=args.server,
        port=args.port,
        mode=args.mode,
        rate=args.rate,
        duration=args.duration,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
