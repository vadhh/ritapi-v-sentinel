#!/usr/bin/env python3
"""
MiniFW-AI Real Traffic Simulator

This script generates REAL DNS queries through dnsmasq to test the full
detection pipeline:

    [This Script] → DNS query → [dnsmasq:53] → logs → [MiniFW Daemon] → [nftables block]

This tests the actual firewall behavior, not just the dashboard display.

Requirements:
    pip install dnspython

Usage:
    # Basic attack simulation (sends 20 malicious DNS queries)
    python real_traffic_simulator.py
    
    # Heavy simulation with 100 queries
    python real_traffic_simulator.py --count 100
    
    # Target specific DNS server
    python real_traffic_simulator.py --dns-server 127.0.0.1
    
    # Burst attack from single "attacker"
    python real_traffic_simulator.py --burst --count 50
"""

import socket
import random
import time
import argparse
import struct
from datetime import datetime


# ============================================================================
# MALICIOUS DOMAINS TO QUERY
# These should trigger the MiniFW detection rules
# ============================================================================

ATTACK_DOMAINS = {
    "malware": [
        "malware-payload.evil.ru",
        "dropper.badactor.cn",
        "c2-server.darkweb.onion",
        "ransomware-key.cryptolocked.net",
        "botnet-cmd.zombienet.xyz",
        "trojan-loader.infected.biz",
        "keylogger-upload.steal.io",
        "backdoor.rootkit.space",
    ],
    "crypto_mining": [
        "coinhive.com",
        "minero.cc",
        "crypto-loot.pro",
        "miner.eth-pool.xyz",
        "xmr-pool.cryptojack.io",
        "monero-miner.web3hack.net",
    ],
    "phishing": [
        "g00gle-secure.login.ml",
        "facebook-verify.account.tk",
        "paypa1-security.update.cf",
        "microsoft-365.reset.ga",
        "apple-id.verify.gq",
    ],
    "gambling": [
        # These match the deny patterns: *.casino*, *.judionline*, *.slot*
        "www.casino-royale-online.com",
        "best-casino-games.net",
        "play.slotmachine24.net",
        "bet.judionline-terbaik.xyz",
        "mega-slots-casino.com",
        "lucky-casino-wins.io",
    ],
    "exfiltration": [
        "upload.data-exfil.cc",
        "files.stolen-docs.ru",
        "exfil.corporate-secrets.io",
        "sync.private-keys.onion",
    ],
    "command_control": [
        "beacon.apt29-infra.ru",
        "callback.lazarus-group.kp",
        "heartbeat.turla-implant.xyz",
        "checkin.apt41-server.io",
    ],
}

# Legitimate domains for baseline traffic
LEGITIMATE_DOMAINS = [
    "www.google.com",
    "www.youtube.com",
    "www.github.com",
    "www.stackoverflow.com",
    "www.wikipedia.org",
    "www.cloudflare.com",
    "www.amazon.com",
    "www.microsoft.com",
]


def build_dns_query(domain: str, query_type: int = 1) -> bytes:
    """
    Build a raw DNS query packet.
    
    Args:
        domain: Domain name to query
        query_type: 1 = A record, 28 = AAAA record
    
    Returns:
        Raw DNS query bytes
    """
    # Transaction ID (random)
    transaction_id = random.randint(0, 65535)
    
    # Flags: standard query, recursion desired
    flags = 0x0100
    
    # Questions: 1, Answers: 0, Authority: 0, Additional: 0
    qdcount = 1
    ancount = 0
    nscount = 0
    arcount = 0
    
    # Build header
    header = struct.pack('>HHHHHH', 
        transaction_id, flags, qdcount, ancount, nscount, arcount)
    
    # Build question section
    question = b''
    for part in domain.split('.'):
        question += bytes([len(part)]) + part.encode('ascii')
    question += b'\x00'  # End of domain name
    question += struct.pack('>HH', query_type, 1)  # Type A, Class IN
    
    return header + question


def send_dns_query(domain: str, dns_server: str = "127.0.0.1", port: int = 53, 
                   timeout: float = 2.0, verbose: bool = False) -> dict:
    """
    Send an actual DNS query to the specified server.
    
    Args:
        domain: Domain to query
        dns_server: DNS server IP address
        port: DNS port (usually 53)
        timeout: Query timeout in seconds
        verbose: Print detailed output
    
    Returns:
        Dict with query result info
    """
    result = {
        "domain": domain,
        "server": dns_server,
        "success": False,
        "response_code": None,
        "error": None,
        "time_ms": 0,
    }
    
    try:
        # Build DNS query
        query = build_dns_query(domain)
        
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        start_time = time.time()
        
        # Send query
        sock.sendto(query, (dns_server, port))
        
        # Receive response
        response, addr = sock.recvfrom(512)
        
        end_time = time.time()
        result["time_ms"] = round((end_time - start_time) * 1000, 2)
        
        # Parse response code from header
        if len(response) >= 12:
            flags = struct.unpack('>H', response[2:4])[0]
            rcode = flags & 0x000F
            result["response_code"] = rcode
            result["success"] = True
            
            # Response codes
            rcode_names = {
                0: "NOERROR",
                1: "FORMERR", 
                2: "SERVFAIL",
                3: "NXDOMAIN",
                4: "NOTIMP",
                5: "REFUSED",
            }
            result["rcode_name"] = rcode_names.get(rcode, f"UNKNOWN({rcode})")
        
        sock.close()
        
    except socket.timeout:
        result["error"] = "TIMEOUT"
    except socket.error as e:
        result["error"] = f"SOCKET_ERROR: {e}"
    except Exception as e:
        result["error"] = f"ERROR: {e}"
    
    if verbose:
        status = "✅" if result["success"] else "❌"
        if result["success"]:
            print(f"  {status} {domain:45} → {result['rcode_name']:10} ({result['time_ms']}ms)")
        else:
            print(f"  {status} {domain:45} → {result['error']}")
    
    return result


def run_attack_simulation(
    dns_server: str = "127.0.0.1",
    port: int = 53,
    count: int = 20,
    delay: float = 0.5,
    attack_types: list = None,
    include_legitimate: bool = True,
    burst_mode: bool = False,
    verbose: bool = True
):
    """
    Run attack simulation by sending real DNS queries.
    
    Args:
        dns_server: DNS server to query
        port: DNS port
        count: Number of queries to send
        delay: Delay between queries (seconds)
        attack_types: List of attack types to include
        include_legitimate: Mix in some legitimate traffic
        burst_mode: Send queries as fast as possible (no delay)
        verbose: Print detailed output
    """
    
    print(f"🔥 MiniFW-AI Real Traffic Simulator")
    print(f"=" * 55)
    print(f"🎯 Target DNS: {dns_server}:{port}")
    print(f"📊 Query count: {count}")
    print(f"⏱️  Delay: {delay}s" + (" (BURST MODE!)" if burst_mode else ""))
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Build domain list
    if attack_types is None:
        attack_types = list(ATTACK_DOMAINS.keys())
    
    domains_to_query = []
    for attack_type in attack_types:
        domains_to_query.extend(ATTACK_DOMAINS.get(attack_type, []))
    
    if include_legitimate:
        # Add 20% legitimate traffic
        num_legit = max(1, count // 5)
        domains_to_query.extend(LEGITIMATE_DOMAINS * (num_legit // len(LEGITIMATE_DOMAINS) + 1))
    
    # Shuffle and pick 'count' domains
    random.shuffle(domains_to_query)
    if len(domains_to_query) < count:
        # Repeat domains if we don't have enough
        domains_to_query = (domains_to_query * (count // len(domains_to_query) + 1))[:count]
    else:
        domains_to_query = domains_to_query[:count]
    
    # Send queries
    print(f"📡 Sending DNS queries...")
    print()
    
    results = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "blocked_likely": 0,  # NXDOMAIN or REFUSED might indicate blocking
    }
    
    actual_delay = 0 if burst_mode else delay
    
    for i, domain in enumerate(domains_to_query, 1):
        if verbose:
            print(f"[{i:3}/{count}]", end="")
        
        result = send_dns_query(
            domain=domain,
            dns_server=dns_server,
            port=port,
            verbose=verbose
        )
        
        results["total"] += 1
        if result["success"]:
            results["success"] += 1
            if result["response_code"] in [3, 5]:  # NXDOMAIN or REFUSED
                results["blocked_likely"] += 1
        else:
            results["failed"] += 1
        
        if actual_delay > 0 and i < len(domains_to_query):
            time.sleep(actual_delay)
    
    # Summary
    print()
    print(f"=" * 55)
    print(f"📊 Results Summary")
    print(f"   Total queries:     {results['total']}")
    print(f"   Successful:        {results['success']}")
    print(f"   Failed/Timeout:    {results['failed']}")
    print(f"   Likely blocked:    {results['blocked_likely']} (NXDOMAIN/REFUSED)")
    print()
    print(f"💡 Check the dashboard at http://localhost:8080/admin/events")
    print(f"   to see if these queries were detected and blocked!")
    print()
    
    return results


def check_dns_server(dns_server: str, port: int = 53) -> bool:
    """Check if DNS server is reachable."""
    print(f"🔍 Checking DNS server {dns_server}:{port}...")
    
    result = send_dns_query("google.com", dns_server, port, timeout=3.0)
    
    if result["success"]:
        print(f"   ✅ DNS server is responding ({result['time_ms']}ms)")
        return True
    else:
        print(f"   ❌ DNS server not responding: {result['error']}")
        print(f"   Make sure dnsmasq is running: docker ps | grep minifw_dns")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="MiniFW-AI Real Traffic Simulator - Sends actual DNS queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic attack simulation
  python real_traffic_simulator.py
  
  # Send 100 malicious queries
  python real_traffic_simulator.py --count 100
  
  # Burst mode (fast, no delay)
  python real_traffic_simulator.py --burst --count 50
  
  # Only gambling site queries
  python real_traffic_simulator.py --attack-types gambling
  
  # Quiet mode (less output)
  python real_traffic_simulator.py --quiet

Note: The DNS server (dnsmasq) must be running for this to work.
Check with: docker ps | grep minifw_dns
        """
    )
    
    parser.add_argument(
        "--dns-server",
        default="127.0.0.1",
        help="DNS server to query (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=53,
        help="DNS port (default: 53)"
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=20,
        help="Number of queries to send (default: 20)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=0.5,
        help="Delay between queries in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Burst mode - send queries as fast as possible"
    )
    parser.add_argument(
        "--attack-types",
        nargs="+",
        choices=list(ATTACK_DOMAINS.keys()),
        help="Specific attack types to simulate"
    )
    parser.add_argument(
        "--no-legitimate",
        action="store_true",
        help="Don't include legitimate traffic in the mix"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode - less output"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check if DNS server is reachable"
    )
    
    args = parser.parse_args()
    
    # Check DNS server first
    if not check_dns_server(args.dns_server, args.port):
        if args.check_only:
            return
        print("\n⚠️  Proceeding anyway, but queries may fail...\n")
    
    if args.check_only:
        return
    
    print()
    
    # Run simulation
    run_attack_simulation(
        dns_server=args.dns_server,
        port=args.port,
        count=args.count,
        delay=args.delay,
        attack_types=args.attack_types,
        include_legitimate=not args.no_legitimate,
        burst_mode=args.burst,
        verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
