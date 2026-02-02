#!/usr/bin/env python3
"""
MiniFW-AI Attack Simulation Script

This generates simulated network security events to test the dashboard.
It creates realistic attack scenarios including:
- Malware domain access
- Crypto mining detection  
- Phishing attempts
- Data exfiltration patterns
- DNS tunneling
- Gambling/casino sites access
- High-frequency burst attacks

Usage:
    # Quick test with 50 events
    python simulate_attack.py --events 50
    
    # Heavy attack simulation with 500 events + scenarios
    python simulate_attack.py --events 500 --scenarios
    
    # Overwrite existing events
    python simulate_attack.py --events 200 --overwrite
    
    # For Docker:
    docker exec minifw_web python3 /app/scripts/simulate_attack.py --output /app/logs/events.jsonl --events 200 --scenarios
"""

import json
import random
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ============================================================================
# ATTACK SCENARIOS CONFIGURATION
# ============================================================================

MALICIOUS_DOMAINS = {
    "malware": [
        "malware-payload.evil.ru",
        "dropper.badactor.cn", 
        "c2-server.darkweb.onion",
        "ransomware-key.cryptolocked.net",
        "botnet-cmd.zombienet.xyz",
        "trojan-loader.infected.biz",
        "keylogger-upload.steal.io",
        "backdoor.rootkit.space",
        "exploit-kit.hackzone.to",
        "fileless-malware.memonly.cc",
    ],
    "crypto_mining": [
        "coinhive.com",
        "minero.cc", 
        "crypto-loot.pro",
        "coin-hive.com",
        "miner.eth-pool.xyz",
        "xmr-pool.cryptojack.io",
        "monero-miner.web3hack.net",
        "browser-mine.js.ninja",
        "pooled-mining.darknet.ru",
        "stealth-miner.shadow.cc",
    ],
    "phishing": [
        "g00gle-secure.login.ml",
        "facebook-verify.account.tk",
        "paypa1-security.update.cf",
        "microsoft-365.reset.ga",
        "apple-id.verify.gq",
        "instagram-login.secure.ml",
        "netflix-payment.update.tk",
        "amazon-order.confirm.cf",
        "twitter-suspended.verify.ga",
        "bank-security.update.gq",
    ],
    "exfiltration": [
        "upload.data-exfil.cc",
        "files.stolen-docs.ru",
        "dump.creditcard-db.cn",
        "leak.customer-data.xyz",
        "exfil.corporate-secrets.io",
        "transfer.sensitive-files.biz",
        "extract.passwords-db.net",
        "sync.private-keys.onion",
        "backup.stolen-creds.space",
        "archive.internal-docs.cc",
    ],
    "dns_tunneling": [
        "dGhpcyBpcyBhIHRlc3Q.tunnel.covert-channel.io",
        "c2VjcmV0LWRhdGE.dns.hidden-transfer.cc",
        "ZXhmaWwtcGF5bG9hZA.out.stealth-dns.net",
        "Y29tbWFuZC1hbmQtY29udHJvbA.c2.dark-channel.xyz",
        "aGlkZGVuLXRyYWZmaWM.vpn.tunnel-master.biz",
    ],
    "gambling": [
        "www.casino-royale-online.com",
        "play.slot-machines24.net",
        "bet.judionline-terbaik.xyz",
        "win.poker-stars-clone.cc",
        "jackpot.casino-mega-wins.io",
        "slots.golden-casino.biz",
        "roulette.vegas-online.tk",
        "blackjack.card-games24.ml",
    ],
    "command_control": [
        "beacon.apt29-infra.ru",
        "callback.lazarus-group.kp",
        "update.cozy-bear-ops.cn",
        "sync.fancy-bear-c2.net",
        "heartbeat.turla-implant.xyz",
        "checkin.apt41-server.io",
        "task.wizard-spider.cc",
        "response.sandworm-team.biz",
    ],
}

ATTACK_REASONS = {
    "malware": ["dns_denied_domain", "asn_denied"],
    "crypto_mining": ["dns_denied_domain", "burst_behavior"],
    "phishing": ["dns_denied_domain", "tls_sni_denied_domain"],
    "exfiltration": ["dns_denied_domain", "burst_behavior", "asn_denied"],
    "dns_tunneling": ["dns_denied_domain", "burst_behavior"],
    "gambling": ["dns_denied_domain"],
    "command_control": ["dns_denied_domain", "asn_denied", "tls_sni_denied_domain"],
}

# Per-segment score ranges that would trigger block/monitor
SEGMENT_CONFIG = {
    "student": {"block_min": 40, "monitor_min": 20, "subnet_prefix": "10.10"},
    "staff": {"block_min": 80, "monitor_min": 60, "subnet_prefix": "10.20"},
    "admin": {"block_min": 90, "monitor_min": 70, "subnet_prefix": "10.30"},
    "default": {"block_min": 60, "monitor_min": 40, "subnet_prefix": "192.168"},
}


def generate_ip(segment: str) -> str:
    """Generate a random IP for the given segment."""
    config = SEGMENT_CONFIG.get(segment, SEGMENT_CONFIG["default"])
    prefix = config["subnet_prefix"]
    
    if prefix == "10.10":
        return f"10.10.{random.randint(1, 254)}.{random.randint(1, 254)}"
    elif prefix == "10.20":
        return f"10.20.{random.randint(1, 254)}.{random.randint(1, 254)}"
    elif prefix == "10.30":
        return f"10.30.{random.randint(1, 254)}.{random.randint(1, 254)}"
    else:
        return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"


def generate_timestamp(base_time: datetime = None, offset_seconds: int = 0) -> str:
    """Generate ISO formatted timestamp."""
    if base_time is None:
        base_time = datetime.now(timezone.utc)
    ts = base_time + timedelta(seconds=offset_seconds)
    return ts.isoformat()


def generate_attack_event(
    attack_type: str,
    segment: str = None,
    action: str = None,
    timestamp: datetime = None
) -> dict:
    """Generate a single attack event."""
    
    if segment is None:
        segment = random.choice(list(SEGMENT_CONFIG.keys()))
    
    config = SEGMENT_CONFIG[segment]
    client_ip = generate_ip(segment)
    
    # Select random domain from attack type
    domains = MALICIOUS_DOMAINS.get(attack_type, MALICIOUS_DOMAINS["malware"])
    domain = random.choice(domains)
    
    # Determine action and score based on segment thresholds
    if action is None:
        action = random.choices(["block", "monitor", "allow"], weights=[0.6, 0.3, 0.1])[0]
    
    if action == "block":
        score = random.randint(config["block_min"], 100)
        reasons = ATTACK_REASONS.get(attack_type, ["dns_denied_domain"])
    elif action == "monitor":
        score = random.randint(config["monitor_min"], config["block_min"] - 1)
        reasons = ATTACK_REASONS.get(attack_type, ["dns_denied_domain"])[:1]
    else:
        score = random.randint(0, config["monitor_min"] - 1)
        reasons = []
    
    return {
        "ts": generate_timestamp(timestamp),
        "segment": segment,
        "client_ip": client_ip,
        "domain": domain,
        "action": action,
        "score": score,
        "reasons": reasons,
    }


def generate_burst_attack(
    client_ip: str,
    segment: str,
    num_requests: int = 50,
    base_time: datetime = None
) -> list:
    """Generate a burst attack simulation - high frequency requests from single IP."""
    
    if base_time is None:
        base_time = datetime.now(timezone.utc)
    
    events = []
    config = SEGMENT_CONFIG[segment]
    
    # First few requests might pass through
    for i in range(min(5, num_requests)):
        events.append({
            "ts": generate_timestamp(base_time, offset_seconds=i),
            "segment": segment,
            "client_ip": client_ip,
            "domain": random.choice(MALICIOUS_DOMAINS["dns_tunneling"]),
            "action": "monitor",
            "score": random.randint(config["monitor_min"], config["block_min"] - 1),
            "reasons": ["burst_behavior"],
        })
    
    # Then escalate to block
    for i in range(5, num_requests):
        events.append({
            "ts": generate_timestamp(base_time, offset_seconds=i),
            "segment": segment,
            "client_ip": client_ip,
            "domain": random.choice(MALICIOUS_DOMAINS["dns_tunneling"]),
            "action": "block",
            "score": random.randint(config["block_min"], 100),
            "reasons": ["dns_denied_domain", "burst_behavior"],
        })
    
    return events


def generate_lateral_movement_attack(
    base_time: datetime = None,
    num_hosts: int = 10
) -> list:
    """Simulate lateral movement - multiple hosts in same segment getting compromised."""
    
    if base_time is None:
        base_time = datetime.now(timezone.utc)
    
    events = []
    segment = "staff"  # Typically lateral movement targets internal networks
    
    c2_domains = MALICIOUS_DOMAINS["command_control"]
    
    for i in range(num_hosts):
        client_ip = generate_ip(segment)
        # Each compromised host beacons back to C2
        for j in range(random.randint(2, 5)):
            events.append({
                "ts": generate_timestamp(base_time, offset_seconds=i*10 + j*2),
                "segment": segment,
                "client_ip": client_ip,
                "domain": random.choice(c2_domains),
                "action": "block",
                "score": random.randint(80, 100),
                "reasons": ["dns_denied_domain", "asn_denied", "tls_sni_denied_domain"],
            })
    
    return events


def run_simulation(
    output_path: str,
    num_events: int = 100,
    attack_mix: dict = None,
    include_scenarios: bool = True,
    append: bool = True,
    delay: float = 0.0
):
    """
    Run the attack simulation and write events to the log file.
    
    Args:
        output_path: Path to events.jsonl file
        num_events: Number of random events to generate
        attack_mix: Dict of attack_type -> weight (e.g., {"malware": 0.3, "phishing": 0.2})
        include_scenarios: Whether to include scenario-based attacks (burst, lateral)
        append: Whether to append to existing file or overwrite
        delay: Delay between writes (for real-time simulation effect)
    """
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Default attack mix
    if attack_mix is None:
        attack_mix = {
            "malware": 0.20,
            "crypto_mining": 0.10,
            "phishing": 0.20,
            "exfiltration": 0.10,
            "dns_tunneling": 0.10,
            "gambling": 0.15,
            "command_control": 0.15,
        }
    
    events = []
    base_time = datetime.now(timezone.utc)
    
    print(f"🔥 MiniFW-AI Attack Simulator")
    print(f"=" * 50)
    print(f"📁 Output: {output_path}")
    print(f"📊 Random events: {num_events}")
    print(f"🎯 Attack types: {list(attack_mix.keys())}")
    print(f"📌 Include scenarios: {include_scenarios}")
    print()
    
    # Generate random attack events
    print(f"⚡ Generating {num_events} random attack events...")
    attack_types = list(attack_mix.keys())
    weights = list(attack_mix.values())
    
    for i in range(num_events):
        attack_type = random.choices(attack_types, weights=weights)[0]
        segment = random.choice(list(SEGMENT_CONFIG.keys()))
        event = generate_attack_event(
            attack_type=attack_type,
            segment=segment,
            timestamp=base_time + timedelta(seconds=i * random.uniform(1, 10))
        )
        events.append(event)
    
    # Add scenario-based attacks
    if include_scenarios:
        print(f"🎭 Adding attack scenarios...")
        
        # Burst attack from suspicious student
        burst_ip = generate_ip("student")
        burst_events = generate_burst_attack(
            client_ip=burst_ip,
            segment="student",
            num_requests=30,
            base_time=base_time + timedelta(minutes=1)
        )
        events.extend(burst_events)
        print(f"   └── Burst attack: {len(burst_events)} events from {burst_ip}")
        
        # Lateral movement in staff network
        lateral_events = generate_lateral_movement_attack(
            base_time=base_time + timedelta(minutes=5),
            num_hosts=8
        )
        events.extend(lateral_events)
        print(f"   └── Lateral movement: {len(lateral_events)} events across 8 hosts")
    
    # Sort by timestamp
    events.sort(key=lambda e: e["ts"])
    
    # Write events
    mode = "a" if append else "w"
    print(f"\n📝 Writing {len(events)} events to {output_path}...")
    
    with open(output_file, mode) as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
            if delay > 0:
                time.sleep(delay)
    
    print(f"\n✅ Simulation complete!")
    print(f"   Total events written: {len(events)}")
    
    # Summary statistics
    action_counts = {}
    segment_counts = {}
    for e in events:
        action_counts[e["action"]] = action_counts.get(e["action"], 0) + 1
        segment_counts[e["segment"]] = segment_counts.get(e["segment"], 0) + 1
    
    print(f"\n📊 Summary:")
    print(f"   Actions:")
    for action, count in sorted(action_counts.items()):
        print(f"      {action}: {count}")
    print(f"   Segments:")
    for seg, count in sorted(segment_counts.items()):
        print(f"      {seg}: {count}")
    
    return events


def main():
    parser = argparse.ArgumentParser(
        description="MiniFW-AI Attack Simulation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with 50 events
  python simulate_attack.py --events 50
  
  # Heavy attack simulation with 500 events
  python simulate_attack.py --events 500 --scenarios
  
  # Real-time simulation (with delay between events)
  python simulate_attack.py --events 100 --delay 0.1
  
  # Overwrite existing events
  python simulate_attack.py --events 200 --overwrite
  
  # For Docker container:
  docker exec minifw_web python3 /app/scripts/simulate_attack.py \\
      --output /app/logs/events.jsonl --events 200 --scenarios
        """
    )
    
    parser.add_argument(
        "-o", "--output",
        default="logs/events.jsonl",
        help="Path to events.jsonl file (default: logs/events.jsonl)"
    )
    parser.add_argument(
        "-n", "--events",
        type=int,
        default=100,
        help="Number of random events to generate (default: 100)"
    )
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Include attack scenarios (burst, lateral movement)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing events file instead of appending"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between writing events (for real-time effect)"
    )
    
    args = parser.parse_args()
    
    run_simulation(
        output_path=args.output,
        num_events=args.events,
        include_scenarios=args.scenarios,
        append=not args.overwrite,
        delay=args.delay
    )


if __name__ == "__main__":
    main()
