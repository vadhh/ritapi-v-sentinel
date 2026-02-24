#!/usr/bin/env python3
"""
Standalone Flow Collector Test - No Gateway Required
Works on single computer without dnsmasq or network traffic

This script simulates the integration between MiniFW-AI components
and flow collector using synthetic data that mimics real patterns.

Usage:
    python3 test_standalone_integration.py [flow_count]
    
Example:
    python3 test_standalone_integration.py 500
"""
import pytest

pytestmark = pytest.mark.integration

import sys
import os
import json
import time
import random
from pathlib import Path

# Add app to path
script_dir = Path(__file__).parent.parent  # Go up to project root
app_dir = script_dir / 'app'
sys.path.insert(0, str(app_dir))

from minifw_ai.collector_flow import FlowTracker, build_feature_vector_24

# Configuration
try:
    FLOW_COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 500
except (ValueError, IndexError):
    # Pytest passes its own args; default to 500 for collection phase
    FLOW_COUNT = 500
OUTPUT_DIR = Path("./data/testing_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Only run script logic if executed directly (not during pytest collection)
if __name__ == '__main__':
    print("=" * 70)
    print("MiniFW-AI Standalone Integration Test")
    print("Flow Collector + Decision Logic (No Gateway Required)")
    print("=" * 70)
    print()
    print(f"Target flows: {FLOW_COUNT}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()
    print("This test simulates:")
    print("  1. DNS queries from clients")
    print("  2. Flow tracking and feature extraction")
    print("  3. MiniFW-AI decision logic (allow/monitor/block)")
    print("  4. Flow record export with labels")
    print()
    print("=" * 70)
    print()

    # Simulated domain lists (matching MiniFW-AI feeds)
    THREAT_DOMAINS = [
    'slot-gacor.xyz',
    'judi-online.net',
    'casino-indo.com',
    'poker-online.id',
    'bandar-togel.com',
    'situs-judi.net',
    'slot-pulsa.xyz',
    'agen-judi.id',
    ]

    NORMAL_DOMAINS = [
    'google.com',
    'facebook.com',
    'youtube.com',
    'github.com',
    'stackoverflow.com',
    'reddit.com',
    'twitter.com',
    'instagram.com',
    'linkedin.com',
    'wikipedia.org',
    'microsoft.com',
    'apple.com',
    'amazon.com',
    ]

    # Simulate client segments
    SEGMENTS = {
    'student': ['10.10.{}.{}'.format(random.randint(1, 255), random.randint(1, 255)) for _ in range(50)],
    'staff': ['10.20.{}.{}'.format(random.randint(1, 255), random.randint(1, 255)) for _ in range(30)],
    'admin': ['10.30.{}.{}'.format(random.randint(1, 255), random.randint(1, 255)) for _ in range(20)],
    }

    # Decision thresholds (from policy.json)
    THRESHOLDS = {
    'student': {'block': 60, 'monitor': 40},
    'staff': {'block': 80, 'monitor': 60},
    'admin': {'block': 90, 'monitor': 70},
    }

    def get_segment_for_ip(ip: str) -> str:
        """Determine segment based on IP"""
        for segment, ips in SEGMENTS.items():
            if ip in ips:
                return segment
        return 'default'

    def is_threat_domain(domain: str) -> bool:
        """Check if domain is in threat list"""
        return any(threat in domain for threat in THREAT_DOMAINS)

    def calculate_score(domain: str, burst_high: bool) -> tuple:
        """Calculate MiniFW-AI style score"""
        score = 0
        reasons = []

        if is_threat_domain(domain):
            score += 40
            reasons.append('threat_domain')

        if burst_high:
            score += 10
            reasons.append('burst_behavior')

        return score, reasons

    def make_decision(score: int, segment: str) -> str:
        """Make allow/monitor/block decision"""
        threshold = THRESHOLDS.get(segment, THRESHOLDS['student'])

        if score >= threshold['block']:
            return 'block'
        elif score >= threshold['monitor']:
            return 'monitor'
        return 'allow'

    def generate_flow_with_context(flow_id: int, tracker: FlowTracker):
        """Generate a flow with realistic context"""

        # Pick segment and client
        segment = random.choice(list(SEGMENTS.keys()))
        client_ip = random.choice(SEGMENTS[segment])

        # Pick domain (70% normal, 30% threat for balanced dataset)
        is_threat = random.random() < 0.3
        domain = random.choice(THREAT_DOMAINS if is_threat else NORMAL_DOMAINS)

        # Generate destination
        dst_ip = f"{random.randint(1, 223)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
        dst_port = 443 if random.random() < 0.7 else random.choice([80, 8080, 3000])
        proto = 'tcp'

        # Determine traffic pattern based on threat/normal
        if is_threat:
            pattern = 'bot_traffic'
            duration = random.uniform(1, 5)
            pkt_count = random.randint(50, 500)
            pkt_size_range = (60, 200)
            burst_factor = 3.0
        else:
            pattern_type = random.choice(['web', 'streaming', 'gaming'])

            if pattern_type == 'web':
                pattern = 'normal_web'
                duration = random.uniform(2, 30)
                pkt_count = random.randint(20, 150)
                pkt_size_range = (500, 1500)
                burst_factor = 1.2
            elif pattern_type == 'streaming':
                pattern = 'streaming'
                duration = random.uniform(30, 600)
                pkt_count = random.randint(200, 2000)
                pkt_size_range = (1200, 1500)
                burst_factor = 1.0
            else:
                pattern = 'gaming'
                duration = random.uniform(60, 1200)
                pkt_count = random.randint(100, 1000)
                pkt_size_range = (50, 150)
                burst_factor = 1.1

        # Create flow
        flow = tracker.update_flow(client_ip, dst_ip, dst_port, proto)
        flow.domain = domain
        flow.first_seen = time.time() - duration
        flow.last_seen = time.time()

        if dst_port == 443:
            flow.sni = domain
            flow.tls_seen = True

        # Simulate packets
        time_per_pkt = duration / pkt_count if pkt_count > 0 else 0.1

        for i in range(pkt_count):
            pkt_size = random.randint(*pkt_size_range)

            if random.random() < (burst_factor - 1.0):
                iat = time_per_pkt * random.uniform(0.01, 0.1)
            else:
                iat = time_per_pkt * random.uniform(0.8, 1.5)

            flow.update(pkt_size, direction='out' if i % 2 == 0 else 'in')

            if flow.last_pkt_time:
                flow.interarrival_times.append(iat * 1000)

        # Calculate MiniFW-AI decision
        burst_high = flow.get_max_burst_pkts_1s() > 50
        score, reasons = calculate_score(domain, burst_high)
        action = make_decision(score, segment)

        features = build_feature_vector_24(flow)

        if action == 'block':
            label = 1
            label_reason = 'blocked_by_minifw'
        elif is_threat:
            label = 1
            label_reason = 'threat_domain'
        elif score >= 50:
            label = 1
            label_reason = 'high_score'
        else:
            label = 0
            label_reason = 'normal_traffic'

        return {
            'flow_id': flow_id,
            'timestamp': flow.first_seen,
            'pattern': pattern,
            'segment': segment,
            'client_ip': client_ip,
            'dst_ip': dst_ip,
            'dst_port': dst_port,
            'proto': proto,
            'domain': domain,
            'sni': flow.sni,
            'duration': flow.get_duration(),
            'packets': flow.pkt_count,
            'bytes': flow.get_total_bytes(),
            'features': features,
            'score': score,
            'reasons': reasons,
            'action': action,
            'label': label,
            'label_reason': label_reason,
        }

    def main():
        """Main test function"""

        print("[INFO] Initializing flow tracker...")
        tracker = FlowTracker()

        print(f"[INFO] Generating {FLOW_COUNT} flows with MiniFW-AI decisions...")
        print()

        records = []
        stats = {
            'allow': 0,
            'monitor': 0,
            'block': 0,
            'threats': 0,
            'normal': 0,
        }

        for i in range(FLOW_COUNT):
            record = generate_flow_with_context(i, tracker)
            records.append(record)

            stats[record['action']] += 1
            if record['label'] == 1:
                stats['threats'] += 1
            else:
                stats['normal'] += 1

            if (i + 1) % 50 == 0:
                print(f"  Generated {i + 1}/{FLOW_COUNT} flows...")

        print()
        print("[INFO] Exporting records...")

        jsonl_file = OUTPUT_DIR / "flow_records.jsonl"
        with jsonl_file.open('w') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"✓ Saved JSONL: {jsonl_file}")

        import csv

        feature_names = [
            "duration_sec", "pkt_count_total", "bytes_total", "bytes_per_sec",
            "pkts_per_sec", "avg_pkt_size", "pkt_size_std", "inbound_outbound_ratio",
            "max_burst_pkts_1s", "max_burst_bytes_1s", "interarrival_mean_ms",
            "interarrival_std_ms", "interarrival_p95_ms", "small_pkt_ratio",
            "tls_seen", "tls_handshake_time_ms", "ja3_hash_bucket", "sni_len",
            "alpn_h2", "cert_self_signed_suspect",
            "dns_seen", "fqdn_len", "subdomain_depth", "domain_repeat_5min"
        ]

        csv_file = OUTPUT_DIR / "flow_records_labeled.csv"
        with csv_file.open('w', newline='') as f:
            fieldnames = [
                'flow_id', 'timestamp', 'pattern', 'segment',
                'client_ip', 'dst_ip', 'dst_port', 'proto',
                'domain', 'sni', 'duration', 'packets', 'bytes',
                'score', 'action'
            ] + feature_names + ['label', 'label_reason']

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for record in records:
                row = {k: v for k, v in record.items() if k != 'features' and k != 'reasons'}
                for i, fname in enumerate(feature_names):
                    row[fname] = record['features'][i]
                writer.writerow(row)

        print(f"✓ Saved CSV: {csv_file}")

        threat_ratio = stats['threats'] / len(records)

        print()
        print("=" * 70)
        print("TEST RESULTS")
        print("=" * 70)
        print(f"Total flows: {len(records)}")
        print(f"  Allow: {stats['allow']}  Monitor: {stats['monitor']}  Block: {stats['block']}")
        print(f"  Normal: {stats['normal']}  Threat: {stats['threats']}")

        if 0.20 <= threat_ratio <= 0.40:
            print("✓ EXCELLENT: Good threat/normal balance")
        elif 0.15 <= threat_ratio <= 0.45:
            print("✓ GOOD: Acceptable threat/normal ratio")
        else:
            print(f"⚠ WARNING: Imbalanced dataset ({threat_ratio*100:.1f}%)")

        print(f"\nJSONL: {jsonl_file}")
        print(f"CSV:   {csv_file}")
        print("✓ Test completed successfully!")

    if __name__ == "__main__":
        main()