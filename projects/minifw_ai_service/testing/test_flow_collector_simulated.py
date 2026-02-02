#!/usr/bin/env python3
"""
Simulated Flow Collector Test - untuk development tanpa root access
Generate synthetic flow data untuk testing feature extraction
"""
import sys
import json
import random
import time
from pathlib import Path

# Add app directory to Python path
script_dir = Path(__file__).parent.parent  # Go up to project root
app_dir = script_dir / 'app'
sys.path.insert(0, str(app_dir))

from minifw_ai.collector_flow import FlowTracker, FlowStats, build_feature_vector_24


def generate_simulated_flows(count: int = 100) -> list[dict]:
    """
    Generate simulated flow data untuk testing
    """
    print(f"Generating {count} simulated flows...")
    
    tracker = FlowTracker()
    
    # Simulate different traffic patterns
    patterns = {
        'normal_web': {
            'ports': [80, 443],
            'pkt_sizes': (500, 1500),
            'pkt_count': (10, 100),
            'duration': (1, 30),
            'burst_low': True
        },
        'streaming': {
            'ports': [443, 8080],
            'pkt_sizes': (1200, 1500),
            'pkt_count': (100, 1000),
            'duration': (30, 300),
            'burst_low': False
        },
        'bot_traffic': {
            'ports': [80, 443, 8080],
            'pkt_sizes': (60, 200),
            'pkt_count': (50, 500),
            'duration': (1, 5),
            'burst_low': False
        },
        'gaming': {
            'ports': [443, 3074, 27015],
            'pkt_sizes': (50, 150),
            'pkt_count': (100, 500),
            'duration': (60, 600),
            'burst_low': True
        }
    }
    
    domains = [
        'google.com', 'facebook.com', 'youtube.com', 'twitter.com',
        'slot-gacor.xyz', 'judi-online.net', 'casino-indo.com',
        'github.com', 'stackoverflow.com', 'reddit.com'
    ]
    
    generated = []
    
    for i in range(count):
        # Random pattern
        pattern_name = random.choice(list(patterns.keys()))
        pattern = patterns[pattern_name]
        
        # Generate flow
        client_ip = f"10.10.{random.randint(1,255)}.{random.randint(1,255)}"
        dst_ip = f"{random.randint(1,223)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        dst_port = random.choice(pattern['ports'])
        proto = 'tcp'
        
        flow = tracker.update_flow(client_ip, dst_ip, dst_port, proto)
        
        # Simulate packets
        pkt_count = random.randint(*pattern['pkt_count'])
        duration = random.uniform(*pattern['duration'])
        
        flow.first_seen = time.time() - duration
        flow.last_seen = time.time()
        
        # Add domain if HTTPS
        if dst_port == 443:
            flow.domain = random.choice(domains)
            flow.sni = flow.domain
            flow.tls_seen = True
        
        # Simulate packet arrivals
        time_per_pkt = duration / pkt_count if pkt_count > 0 else 0.1
        
        for j in range(pkt_count):
            pkt_size = random.randint(*pattern['pkt_sizes'])
            
            # Add some jitter
            if pattern['burst_low']:
                # Regular intervals
                iat = time_per_pkt * random.uniform(0.8, 1.2)
            else:
                # Bursty traffic
                if random.random() < 0.3:  # 30% burst
                    iat = time_per_pkt * random.uniform(0.01, 0.1)
                else:
                    iat = time_per_pkt * random.uniform(1, 2)
            
            flow.update(pkt_size, direction='out' if j % 2 == 0 else 'in')
            
            if flow.last_pkt_time:
                flow.interarrival_times.append(iat * 1000)  # to ms
        
        # Build record
        vector = build_feature_vector_24(flow)
        
        record = {
            'flow_id': i,
            'pattern': pattern_name,
            'client_ip': client_ip,
            'dst_ip': dst_ip,
            'dst_port': dst_port,
            'proto': proto,
            'domain': flow.domain,
            'sni': flow.sni,
            'features': vector,
            'timestamp': flow.first_seen,
            # For future labeling
            'label': None,
            'label_reason': None
        }
        
        generated.append(record)
        
        # Progress
        if (i + 1) % 20 == 0:
            print(f"  Generated {i+1}/{count} flows...")
    
    print(f"✓ Generated {len(generated)} flows\n")
    return generated


def analyze_flow_patterns(records: list[dict]):
    """
    Analyze generated flow patterns
    """
    print("=" * 60)
    print("FLOW PATTERN ANALYSIS")
    print("=" * 60)
    
    patterns = {}
    for record in records:
        pattern = record['pattern']
        if pattern not in patterns:
            patterns[pattern] = []
        patterns[pattern].append(record)
    
    for pattern, flows in patterns.items():
        print(f"\n{pattern.upper()} ({len(flows)} flows)")
        print("-" * 40)
        
        # Get sample
        sample = flows[0]
        features = sample['features']
        
        feature_names = [
            "duration_sec", "pkt_count_total", "bytes_total", "bytes_per_sec",
            "pkts_per_sec", "avg_pkt_size", "pkt_size_std", "inbound_outbound_ratio",
            "max_burst_pkts_1s", "max_burst_bytes_1s", "interarrival_mean_ms",
            "interarrival_std_ms", "interarrival_p95_ms", "small_pkt_ratio",
            "tls_seen", "tls_handshake_time_ms", "ja3_hash_bucket", "sni_len",
            "alpn_h2", "cert_self_signed_suspect",
            "dns_seen", "fqdn_len", "subdomain_depth", "domain_repeat_5min"
        ]
        
        # Key features
        print(f"  Duration:    {features[0]:.2f}s")
        print(f"  Packets:     {features[1]:.0f}")
        print(f"  Bytes:       {features[2]:.0f}")
        print(f"  PPS:         {features[4]:.2f}")
        print(f"  Avg pkt:     {features[5]:.2f}")
        print(f"  Burst pkts:  {features[8]:.0f}")
        print(f"  TLS:         {features[14]:.0f}")


def export_for_training(records: list[dict], output_dir: str = "./data/testing_output"):
    """
    Export flow records untuk training
    """
    print("\n" + "=" * 60)
    print("EXPORTING FOR TRAINING")
    print("=" * 60)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Export raw records (JSONL)
    records_file = output_path / "flow_records.jsonl"
    with records_file.open('w') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"✓ Saved raw records: {records_file}")
    print(f"  Total records: {len(records)}")
    
    # 2. Export feature matrix (CSV format untuk pandas)
    csv_file = output_path / "features.csv"
    
    feature_names = [
        "duration_sec", "pkt_count_total", "bytes_total", "bytes_per_sec",
        "pkts_per_sec", "avg_pkt_size", "pkt_size_std", "inbound_outbound_ratio",
        "max_burst_pkts_1s", "max_burst_bytes_1s", "interarrival_mean_ms",
        "interarrival_std_ms", "interarrival_p95_ms", "small_pkt_ratio",
        "tls_seen", "tls_handshake_time_ms", "ja3_hash_bucket", "sni_len",
        "alpn_h2", "cert_self_signed_suspect",
        "dns_seen", "fqdn_len", "subdomain_depth", "domain_repeat_5min"
    ]
    
    with csv_file.open('w') as f:
        # Header
        header = ['flow_id', 'client_ip', 'dst_ip', 'dst_port', 'domain', 'pattern'] + feature_names + ['label']
        f.write(','.join(header) + '\n')
        
        # Data
        for record in records:
            row = [
                str(record['flow_id']),
                record['client_ip'],
                record['dst_ip'],
                str(record['dst_port']),
                record.get('domain', ''),
                record['pattern']
            ]
            row.extend([str(x) for x in record['features']])
            row.append('')  # label placeholder
            
            f.write(','.join(row) + '\n')
    
    print(f"✓ Saved feature CSV: {csv_file}")
    
    # 3. Show sample records
    print("\n" + "-" * 60)
    print("SAMPLE RECORDS")
    print("-" * 60)
    
    for i in range(min(3, len(records))):
        print(f"\nRecord {i+1}:")
        print(json.dumps(records[i], indent=2))
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print(f"""
1. Review generated data in: {output_dir}

2. Label the data:
   - Open {csv_file}
   - Add labels (0=normal, 1=threat) in 'label' column
   - Use patterns to guide labeling:
     * 'bot_traffic' → likely threat (1)
     * flows to 'slot-gacor.xyz', 'judi-online.net' → threat (1)
     * normal web/streaming → normal (0)

3. Train MLP model (STEP 1.4):
   python3 train_mlp.py --data {csv_file}

4. Test inference:
   python3 test_inference.py --model mlp_model.joblib

5. Integrate to main pipeline
""")


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("MiniFW-AI Flow Collector - SIMULATED TEST")
    print("STEP 1.1: Feature Extraction & Flow Records")
    print("=" * 60)
    print()
    
    # Get sample count from args
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    
    # Generate flows
    records = generate_simulated_flows(count)
    
    # Analyze
    analyze_flow_patterns(records)
    
    # Export
    export_for_training(records)
    
    print("\n✓ Test completed successfully!\n")


if __name__ == "__main__":
    main()