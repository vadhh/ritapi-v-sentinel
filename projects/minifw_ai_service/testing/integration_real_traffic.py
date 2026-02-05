#!/usr/bin/env python3
"""
Real Traffic Testing Script for MiniFW-AI with Flow Collector
This script runs MiniFW-AI with flow collection enabled for testing purposes.

Usage:
    sudo python3 test_real_traffic.py [duration_minutes]
    
Example:
    sudo python3 test_real_traffic.py 5    # Run for 5 minutes
"""
import pytest

pytestmark = pytest.mark.integration

import sys
import os
import signal
import time
from pathlib import Path

# Add app to path
script_dir = Path(__file__).parent.parent  # Go up to project root
app_dir = script_dir / 'app'
sys.path.insert(0, str(app_dir))

# Configuration
try:
    TEST_DURATION_MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 5
except (ValueError, IndexError):
    # Pytest passes its own args; default to 5 for collection phase
    TEST_DURATION_MINUTES = 5
OUTPUT_DIR = Path("./data/testing_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Set environment variables for testing
os.environ["MINIFW_POLICY"] = str(script_dir / "config" / "policy.json")
os.environ["MINIFW_FEEDS"] = str(script_dir / "config" / "feeds")
os.environ["MINIFW_LOG"] = str(OUTPUT_DIR / "events.jsonl")
os.environ["MINIFW_FLOW_RECORDS"] = str(OUTPUT_DIR / "flow_records.jsonl")

# Only run script logic if executed directly (not during pytest collection)
if __name__ == '__main__':
    print("=" * 70)
    print("MiniFW-AI Real Traffic Testing with Flow Collection")
    print("=" * 70)
    print()
    print(f"Test Duration: {TEST_DURATION_MINUTES} minutes")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"  - Events Log: {OUTPUT_DIR / 'events.jsonl'}")
    print(f"  - Flow Records: {OUTPUT_DIR / 'flow_records.jsonl'}")
    print()
    print("Prerequisites:")
    print("  1. dnsmasq should be running and logging queries")
    print("  2. Run this script as root (sudo)")
    print("  3. Network traffic should be flowing through the gateway")
    print()
    print("=" * 70)
    print()

    # Check if running as root
    if os.geteuid() != 0:
    print("ERROR: This script must be run as root")
    print("Usage: sudo python3 test_real_traffic.py")
    sys.exit(1)

    # Check if dnsmasq log exists
    dnsmasq_log = Path("/var/log/dnsmasq.log")
    if not dnsmasq_log.exists():
    print(f"WARNING: DNS log not found at {dnsmasq_log}")
    print("MiniFW-AI may not receive any events")
    print()
    response = input("Continue anyway? [y/N]: ")
    if response.lower() != 'y':
        print("Aborted")
        sys.exit(1)

    # Import and run MiniFW-AI with flow collector
    print("[INFO] Starting MiniFW-AI with flow collection...")
    print()

    # Track if we should stop
    should_stop = False
    start_time = time.time()

    def signal_handler(sig, frame):
    global should_stop
    print("\n\n[INFO] Stopping test...")
    should_stop = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Import the modified main
    sys.path.insert(0, str(script_dir))
    from main_with_flow_collector import run

    # Start monitoring thread
    import threading

    def monitor_progress():
    """Monitor and display progress"""
    elapsed = 0
    while not should_stop and elapsed < (TEST_DURATION_MINUTES * 60):
        time.sleep(10)  # Check every 10 seconds
        elapsed = int(time.time() - start_time)
        
        # Count records
        events_file = OUTPUT_DIR / "events.jsonl"
        flow_records_file = OUTPUT_DIR / "flow_records.jsonl"
        
        event_count = 0
        flow_count = 0
        
        if events_file.exists():
            with events_file.open() as f:
                event_count = sum(1 for _ in f)
        
        if flow_records_file.exists():
            with flow_records_file.open() as f:
                flow_count = sum(1 for _ in f)
        
        minutes_left = TEST_DURATION_MINUTES - (elapsed // 60)
        print(f"[{elapsed // 60}m {elapsed % 60}s] Events: {event_count}, Flow Records: {flow_count}, Time left: {minutes_left}m")

    monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
    monitor_thread.start()

    # Run MiniFW-AI (this will block)
    try:
    # Set a timeout
    def timeout_handler(sig, frame):
        raise TimeoutError("Test duration reached")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TEST_DURATION_MINUTES * 60)
    
    print(f"[INFO] MiniFW-AI running... (Press Ctrl+C to stop early)")
    print()
    
    run()
    
    except TimeoutError:
    print("\n[INFO] Test duration reached")
    except KeyboardInterrupt:
    print("\n[INFO] Test interrupted by user")
    except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

    # Analysis
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    print()

    events_file = OUTPUT_DIR / "events.jsonl"
    flow_records_file = OUTPUT_DIR / "flow_records.jsonl"

    if events_file.exists():
    with events_file.open() as f:
        events = [line for line in f]
    print(f"✓ Events collected: {len(events)}")
    
    if len(events) > 0:
        print(f"  Sample event: {events[0][:100]}...")
    else:
    print("✗ No events collected")
    print("  Check if dnsmasq is running and logging queries")

    print()

    if flow_records_file.exists():
    with flow_records_file.open() as f:
        flows = [line for line in f]
    print(f"✓ Flow records collected: {len(flows)}")
    
    if len(flows) > 0:
        import json
        sample = json.loads(flows[0])
        print(f"  Sample flow:")
        print(f"    Client: {sample['client_ip']}")
        print(f"    Domain: {sample.get('domain', 'N/A')}")
        print(f"    Packets: {sample['packets']}")
        print(f"    Duration: {sample['duration']:.2f}s")
        print(f"    Features: {len(sample['features'])} values")
    else:
    print("✗ No flow records collected")
    print("  This is normal if no DNS queries were processed")

    print()
    print("=" * 70)
    print("OUTPUT FILES")
    print("=" * 70)
    print()
    print(f"Events log: {events_file}")
    print(f"Flow records: {flow_records_file}")
    print()
    print("Next steps:")
    print("  1. Review flow records:")
    print(f"     cat {flow_records_file} | head -5 | python3 -m json.tool")
    print()
    print("  2. Convert to CSV for labeling:")
    print(f"     python3 convert_flows_to_csv.py {flow_records_file}")
    print()
    print("  3. Label the data and train MLP model")
    print()
    print("=" * 70)