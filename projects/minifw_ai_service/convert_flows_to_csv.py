#!/usr/bin/env python3
"""
Convert flow records from JSONL to CSV format for labeling and training

Usage:
    python3 convert_flows_to_csv.py <input_jsonl> [output_csv]
    
Example:
    python3 convert_flows_to_csv.py /tmp/minifw_ai_test_output/flow_records.jsonl
    python3 convert_flows_to_csv.py flow_records.jsonl labeled_flows.csv
"""
import sys
import json
import csv
from pathlib import Path

def convert_jsonl_to_csv(input_file: str, output_file: str = None):
    """Convert JSONL flow records to CSV format"""
    
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Default output file
    if output_file is None:
        output_file = input_path.parent / f"{input_path.stem}_features.csv"
    else:
        output_file = Path(output_file)
    
    print(f"Converting {input_path} to {output_file}")
    print()
    
    # Feature names (24 features)
    feature_names = [
        "duration_sec", "pkt_count_total", "bytes_total", "bytes_per_sec",
        "pkts_per_sec", "avg_pkt_size", "pkt_size_std", "inbound_outbound_ratio",
        "max_burst_pkts_1s", "max_burst_bytes_1s", "interarrival_mean_ms",
        "interarrival_std_ms", "interarrival_p95_ms", "small_pkt_ratio",
        "tls_seen", "tls_handshake_time_ms", "ja3_hash_bucket", "sni_len",
        "alpn_h2", "cert_self_signed_suspect",
        "dns_seen", "fqdn_len", "subdomain_depth", "domain_repeat_5min"
    ]
    
    # CSV header
    header = [
        'flow_id', 'timestamp', 'client_ip', 'dst_ip', 'dst_port', 'proto',
        'domain', 'sni', 'segment', 'packets', 'bytes', 'duration',
        'action', 'score'
    ] + feature_names + ['label', 'label_reason']
    
    # Read and convert
    records_processed = 0
    records_skipped = 0
    
    with input_path.open('r') as fin, output_file.open('w', newline='') as fout:
        writer = csv.DictWriter(fout, fieldnames=header)
        writer.writeheader()
        
        for line_num, line in enumerate(fin, 1):
            try:
                record = json.loads(line.strip())
                
                # Skip if no features
                if 'features' not in record or len(record['features']) != 24:
                    records_skipped += 1
                    continue
                
                # Build CSV row
                row = {
                    'flow_id': records_processed,
                    'timestamp': record.get('timestamp', ''),
                    'client_ip': record.get('client_ip', ''),
                    'dst_ip': record.get('dst_ip', ''),
                    'dst_port': record.get('dst_port', ''),
                    'proto': record.get('proto', ''),
                    'domain': record.get('domain', ''),
                    'sni': record.get('sni', ''),
                    'segment': record.get('segment', ''),
                    'packets': record.get('packets', ''),
                    'bytes': record.get('bytes', ''),
                    'duration': record.get('duration', ''),
                    'action': record.get('action', ''),
                    'score': record.get('score', ''),
                }
                
                # Add features
                for i, fname in enumerate(feature_names):
                    row[fname] = record['features'][i]
                
                # Add label fields (empty for now)
                row['label'] = record.get('label', '')
                row['label_reason'] = record.get('label_reason', '')
                
                writer.writerow(row)
                records_processed += 1
                
                if records_processed % 100 == 0:
                    print(f"  Processed {records_processed} records...")
                
            except json.JSONDecodeError:
                print(f"Warning: Skipping invalid JSON at line {line_num}")
                records_skipped += 1
            except Exception as e:
                print(f"Warning: Error at line {line_num}: {e}")
                records_skipped += 1
    
    print()
    print("=" * 70)
    print("CONVERSION COMPLETE")
    print("=" * 70)
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_file}")
    print(f"  Records processed: {records_processed}")
    print(f"  Records skipped: {records_skipped}")
    print()
    
    if records_processed > 0:
        print("Next steps:")
        print()
        print("1. Open the CSV file for labeling:")
        print(f"   libreoffice {output_file}")
        print(f"   # or nano {output_file}")
        print()
        print("2. Add labels in the 'label' column:")
        print("   - 0 = normal traffic")
        print("   - 1 = threat/suspicious")
        print()
        print("3. Labeling guidelines:")
        print("   - High burst_pkts with small packets → likely bot (1)")
        print("   - Gambling domains (slot, gacor, casino) → threat (1)")
        print("   - Normal web/streaming → normal (0)")
        print("   - Action='block' → likely threat (1)")
        print()
        print("4. Save and use for training:")
        print(f"   python3 train_mlp.py --data {output_file}")
        print()
    else:
        print("No records converted. Check input file format.")
    
    return records_processed

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 convert_flows_to_csv.py <input_jsonl> [output_csv]")
        print()
        print("Examples:")
        print("  python3 convert_flows_to_csv.py /tmp/minifw_ai_test_output/flow_records.jsonl")
        print("  python3 convert_flows_to_csv.py flow_records.jsonl labeled_flows.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_jsonl_to_csv(input_file, output_file)