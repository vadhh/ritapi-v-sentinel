#!/usr/bin/env python3
"""
Test script untuk Flow Collector - STEP 1.1
Mengumpulkan flow_record untuk training MLP Engine

Usage:
    python3 test_flow_collector.py [duration_seconds]
"""
import sys
import time
import json
from pathlib import Path

# Add app directory to Python path
script_dir = Path(__file__).parent.parent  # Go up to project root
app_dir = script_dir / 'app'
sys.path.insert(0, str(app_dir))

from minifw_ai.collector_flow import (
    FlowTracker, 
    stream_conntrack_flows,
    build_feature_vector_24
)
from minifw_ai.collector_dnsmasq import stream_dns_events
from minifw_ai.collector_zeek import stream_zeek_sni_events


def test_basic_flow_tracking(duration: int = 60):
    """
    Test 1: Basic flow tracking dari conntrack
    Mengumpulkan flow statistics selama duration detik
    """
    print(f"[TEST 1] Basic Flow Tracking ({duration}s)")
    print("=" * 60)
    
    tracker = FlowTracker(flow_timeout=300)
    start_time = time.time()
    flow_count = 0
    
    try:
        for src_ip, dst_ip, dst_port, proto in stream_conntrack_flows():
            # Update flow dengan packet size estimate (default 1500 bytes)
            flow = tracker.update_flow(
                client_ip=src_ip,
                dst_ip=dst_ip,
                dst_port=dst_port,
                proto=proto,
                pkt_size=1500  # Simplified: real packet size from pcap/accounting
            )
            
            flow_count += 1
            
            # Print sample flow every 10 flows
            if flow_count % 10 == 0:
                print(f"\n[Flow #{flow_count}]")
                print(f"  Client: {flow.client_ip}")
                print(f"  Destination: {flow.dst_ip}:{flow.dst_port} ({flow.proto})")
                print(f"  Packets: {flow.pkt_count}")
                print(f"  Bytes: {flow.get_total_bytes()}")
                print(f"  Duration: {flow.get_duration():.2f}s")
                print(f"  PPS: {flow.get_pkts_per_sec():.2f}")
                print(f"  BPS: {flow.get_bytes_per_sec():.2f}")
            
            # Stop after duration
            if time.time() - start_time > duration:
                break
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Total flows observed: {flow_count}")
    print(f"Active flows in tracker: {len(tracker.flows)}")
    print()
    
    return tracker


def test_feature_vector_extraction(tracker: FlowTracker):
    """
    Test 2: Extract 24-feature vectors dari flows
    """
    print("[TEST 2] Feature Vector Extraction (24 features)")
    print("=" * 60)
    
    flows = tracker.get_all_active_flows()
    
    if not flows:
        print("No active flows to extract features from")
        return []
    
    print(f"Extracting features from {len(flows)} active flows...\n")
    
    feature_vectors = []
    
    for i, flow in enumerate(flows[:5]):  # Show first 5
        print(f"[Flow {i+1}] {flow.client_ip} -> {flow.dst_ip}:{flow.dst_port}")
        
        vector = build_feature_vector_24(flow)
        feature_vectors.append({
            'client_ip': flow.client_ip,
            'dst_ip': flow.dst_ip,
            'dst_port': flow.dst_port,
            'proto': flow.proto,
            'domain': flow.domain,
            'features': vector
        })
        
        # Print features with labels
        feature_names = [
            # Basic flow (8)
            "duration_sec", "pkt_count_total", "bytes_total", "bytes_per_sec",
            "pkts_per_sec", "avg_pkt_size", "pkt_size_std", "inbound_outbound_ratio",
            # Burst & periodicity (6)
            "max_burst_pkts_1s", "max_burst_bytes_1s", "interarrival_mean_ms",
            "interarrival_std_ms", "interarrival_p95_ms", "small_pkt_ratio",
            # TLS (6)
            "tls_seen", "tls_handshake_time_ms", "ja3_hash_bucket", "sni_len",
            "alpn_h2", "cert_self_signed_suspect",
            # DNS (4)
            "dns_seen", "fqdn_len", "subdomain_depth", "domain_repeat_5min"
        ]
        
        print("  Features:")
        for name, value in zip(feature_names, vector):
            print(f"    {name:25s}: {value:10.2f}")
        print()
    
    print("=" * 60)
    print(f"Total feature vectors extracted: {len(feature_vectors)}")
    print()
    
    return feature_vectors


def test_dns_enrichment(tracker: FlowTracker, duration: int = 30):
    """
    Test 3: Enrich flows dengan DNS data
    """
    print(f"[TEST 3] DNS Enrichment ({duration}s)")
    print("=" * 60)
    
    dns_log = "/var/log/dnsmasq.log"
    
    if not Path(dns_log).exists():
        print(f"DNS log not found: {dns_log}")
        print("Skipping DNS enrichment test")
        return
    
    print(f"Reading DNS queries from: {dns_log}")
    print("Enriching flows with domain information...\n")
    
    start_time = time.time()
    dns_count = 0
    
    try:
        for client_ip, domain in stream_dns_events(dns_log):
            tracker.enrich_with_dns(client_ip, domain)
            dns_count += 1
            
            if dns_count % 5 == 0:
                print(f"  [{dns_count}] {client_ip} -> {domain}")
            
            if time.time() - start_time > duration:
                break
    
    except FileNotFoundError:
        print("DNS log file not found, skipping...")
    except KeyboardInterrupt:
        print("\nInterrupted")
    
    print("\n" + "=" * 60)
    print(f"Total DNS queries processed: {dns_count}")
    
    # Show enriched flows
    enriched = [f for f in tracker.get_all_active_flows() if f.domain]
    print(f"Flows with domain info: {len(enriched)}")
    
    for flow in enriched[:3]:
        print(f"  {flow.client_ip} -> {flow.domain}")
    print()


def export_flow_records(feature_vectors: list[dict], output_path: str):
    """
    Export flow records to JSON file untuk training nanti
    """
    print(f"[EXPORT] Saving flow records to {output_path}")
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Export sebagai JSONL (JSON Lines)
    with output.open('w') as f:
        for record in feature_vectors:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"Exported {len(feature_vectors)} flow records")
    print()


def main():
    """Main test runner"""
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    
    print("\n" + "=" * 60)
    print("MiniFW-AI Flow Collector - STEP 1.1 Test")
    print("=" * 60)
    print()
    
    # Check if running as root (needed for conntrack)
    import os
    if os.geteuid() != 0:
        print("WARNING: Not running as root")
        print("Some features (conntrack) may not work properly")
        print("Run with: sudo python3 test_flow_collector.py")
        print()
        
        # Continue anyway for testing
    
    # Test 1: Basic flow tracking
    tracker = test_basic_flow_tracking(duration=duration)
    
    # Test 2: Feature extraction
    feature_vectors = test_feature_vector_extraction(tracker)
    
    # Test 3: DNS enrichment (if available)
    test_dns_enrichment(tracker, duration=30)
    
    # Re-extract features after enrichment
    print("[RE-EXTRACT] Features after DNS enrichment")
    print("=" * 60)
    all_flows = tracker.get_all_active_flows()
    final_vectors = []
    
    for flow in all_flows:
        vector = build_feature_vector_24(flow)
        final_vectors.append({
            'client_ip': flow.client_ip,
            'dst_ip': flow.dst_ip,
            'dst_port': flow.dst_port,
            'proto': flow.proto,
            'domain': flow.domain,
            'sni': flow.sni,
            'features': vector,
            'timestamp': flow.first_seen
        })
    
    print(f"Total flow records ready: {len(final_vectors)}")
    print()
    
    # Export
    export_flow_records(final_vectors, "./data/flow_records.jsonl")
    
    # Show sample record
    if final_vectors:
        print("[SAMPLE RECORD]")
        print(json.dumps(final_vectors[0], indent=2))
        print()
    
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Collect more samples (target: 5000+ flows)")
    print("2. Label flows as 'threat' or 'normal'")
    print("3. Train MLP model (STEP 1.4)")
    print()


if __name__ == "__main__":
    main()