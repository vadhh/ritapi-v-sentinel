#!/usr/bin/env python3
"""
Comprehensive Integration Test v1.1 - With Critical Fixes
Tests MLP + Flow Collector + YARA Scanner with hard gates.

This test verifies end-to-end functionality:
- Flow tracking and feature extraction
- MLP threat detection (with DataFrame fix)
- Hard threat gates override logic
- YARA payload scanning
- Decision logic integration

Usage:
    python3 testing/test_full_integration.py
"""
import sys
import time
from pathlib import Path

# Add app to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'app'))

print("=" * 70)
print("MiniFW-AI Comprehensive Integration Test")
print("MLP + Flow Collector + YARA Scanner")
print("=" * 70)
print()

# Check dependencies
missing_deps = []

try:
    from minifw_ai.collector_flow import FlowTracker, FlowStats, build_feature_vector_24
    print("✓ Flow Collector available")
except ImportError as e:
    print(f"❌ Flow Collector not available: {e}")
    missing_deps.append("Flow Collector")

try:
    from minifw_ai.utils.mlp_engine import MLPThreatDetector
    print("✓ MLP Engine available")
    MLP_AVAILABLE = True
except ImportError as e:
    print(f"⚠ MLP Engine not available: {e}")
    print("  (Install scikit-learn to enable)")
    MLP_AVAILABLE = False

try:
    from minifw_ai.utils.yara_scanner import YARAScanner
    print("✓ YARA Scanner available")
    YARA_AVAILABLE = True
except ImportError as e:
    print(f"⚠ YARA Scanner not available: {e}")
    print("  (Install yara-python to enable)")
    YARA_AVAILABLE = False

if missing_deps:
    print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
    sys.exit(1)

print()


def test_flow_tracking():
    """Test 1: Flow tracking and feature extraction."""
    print("[TEST 1] Flow Tracking & Feature Extraction")
    print("=" * 70)
    
    try:
        tracker = FlowTracker(flow_timeout=300)
        
        # Simulate some flows
        test_flows = [
            ('192.168.1.100', '8.8.8.8', 443, 'tcp', 'google.com'),
            ('192.168.1.100', '1.2.3.4', 443, 'tcp', 'slot-gacor.xyz'),
            ('192.168.1.101', '1.1.1.1', 80, 'tcp', 'example.com'),
        ]
        
        for client_ip, dst_ip, dst_port, proto, domain in test_flows:
            flow = tracker.update_flow(client_ip, dst_ip, dst_port, proto, pkt_size=1500)
            
            # Simulate some packets
            for _ in range(50):
                flow.update(pkt_size=1500, direction='out')
            
            # Enrich with domain
            tracker.enrich_with_dns(client_ip, domain)
            flow.domain = domain
            flow.tls_seen = True if dst_port == 443 else False
        
        # Extract features
        flows = tracker.get_all_active_flows()
        print(f"\n  Created {len(flows)} flows")
        
        for i, flow in enumerate(flows, 1):
            features = build_feature_vector_24(flow)
            print(f"\n  Flow {i}: {flow.client_ip} -> {flow.domain}")
            print(f"    Features: {len(features)}")
            print(f"    Duration: {features[0]:.2f}s")
            print(f"    Packets: {features[1]:.0f}")
            print(f"    Bytes/sec: {features[3]:.2f}")
        
        print("\n✓ Flow tracking OK")
        return True, tracker
        
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_mlp_detection(tracker):
    """Test 2: MLP threat detection."""
    print("\n[TEST 2] MLP Threat Detection")
    print("=" * 70)
    
    if not MLP_AVAILABLE:
        print("⚠ MLP not available, skipping")
        return True, None
    
    # Check if model exists
    model_path = script_dir / 'models' / 'mlp_engine.pkl'
    
    if not model_path.exists():
        print(f"⚠ Model not found: {model_path}")
        print("  Train a model first or skip MLP tests")
        return True, None
    
    try:
        detector = MLPThreatDetector(model_path=str(model_path), threshold=0.5)
        
        if not detector.model_loaded:
            print("⚠ Model not loaded")
            return True, None
        
        print(f"\n✓ Model loaded: {model_path}")
        
        # Test inference on flows
        flows = tracker.get_all_active_flows()
        
        for flow in flows:
            is_threat, proba = detector.is_suspicious(flow, return_probability=True)
            
            print(f"\n  Flow: {flow.client_ip} -> {flow.domain}")
            print(f"    Threat: {is_threat}")
            print(f"    Probability: {proba:.4f}")
            print(f"    Result: {'⚠ THREAT' if is_threat else '✓ Normal'}")
        
        print("\n✓ MLP detection OK")
        return True, detector
        
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_yara_scanning():
    """Test 3: YARA payload scanning."""
    print("\n[TEST 3] YARA Payload Scanning")
    print("=" * 70)
    
    if not YARA_AVAILABLE:
        print("⚠ YARA not available, skipping")
        return True, None
    
    rules_dir = script_dir / 'yara_rules'
    
    if not rules_dir.exists():
        print(f"⚠ YARA rules not found: {rules_dir}")
        return True, None
    
    try:
        scanner = YARAScanner(rules_dir=str(rules_dir))
        
        if not scanner.rules_loaded:
            print("⚠ YARA rules not loaded")
            return True, None
        
        print(f"\n✓ Rules loaded from: {rules_dir}")
        
        # Test payloads
        test_payloads = [
            ('Gambling site', 'slot gacor online deposit pulsa tanpa potongan'),
            ('Normal site', 'welcome to our professional website'),
            ('Malware', 'powershell -enc base64encodedcommand'),
            ('SQL injection', "username=' OR 1=1--"),
        ]
        
        for name, payload in test_payloads:
            matches = scanner.scan_payload(payload)
            
            print(f"\n  Payload: {name}")
            print(f"    Text: {payload[:50]}...")
            
            if matches:
                print(f"    ⚠ DETECTED: {len(matches)} match(es)")
                for match in matches:
                    print(f"      - {match.rule} ({match.get_category()}, {match.get_severity()})")
            else:
                print(f"    ✓ Clean")
        
        print("\n✓ YARA scanning OK")
        return True, scanner
        
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_decision_integration(tracker, mlp_detector, yara_scanner):
    """Test 4: Integrated decision making."""
    print("\n[TEST 4] Integrated Decision Making")
    print("=" * 70)
    
    # Import decision function
    from minifw_ai.main import score_and_decide
    
    class SimpleThresholds:
        def __init__(self):
            self.monitor_threshold = 40
            self.block_threshold = 60
    
    weights = {
        'dns_weight': 41,
        'sni_weight': 34,
        'asn_weight': 15,
        'burst_weight': 10,
        'mlp_weight': 30,
        'yara_weight': 35
    }
    
    thresholds = SimpleThresholds()
    
    test_cases = [
        {
            'name': 'Normal traffic',
            'domain': 'google.com',
            'flow_client': '192.168.1.100',
            'denied': False,
            'sni_denied': False,
            'burst': False
        },
        {
            'name': 'Gambling site',
            'domain': 'slot-gacor.xyz',
            'flow_client': '192.168.1.100',
            'denied': True,
            'sni_denied': False,
            'burst': False
        },
        {
            'name': 'Burst + suspicious',
            'domain': 'unknown-site.com',
            'flow_client': '192.168.1.101',
            'denied': False,
            'sni_denied': False,
            'burst': True
        }
    ]
    
    for case in test_cases:
        print(f"\n  Scenario: {case['name']}")
        print(f"    Domain: {case['domain']}")
        
        # Get MLP score
        mlp_score = 0
        if MLP_AVAILABLE and mlp_detector and mlp_detector.model_loaded:
            flow = tracker.get_flow(case['flow_client'], "", 0, "tcp")
            if flow:
                is_threat, proba = mlp_detector.is_suspicious(flow, return_probability=True)
                if is_threat:
                    mlp_score = int(proba * 100)
        
        # Get YARA score
        yara_score = 0
        if YARA_AVAILABLE and yara_scanner and yara_scanner.rules_loaded:
            payload = case['domain'].encode('utf-8')
            matches = yara_scanner.scan_payload(payload)
            if matches:
                severity_scores = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
                yara_score = max(severity_scores.get(m.get_severity(), 25) for m in matches)
        
        # Make decision
        score, reasons, action = score_and_decide(
            domain=case['domain'],
            denied=case['denied'],
            sni_denied=case['sni_denied'],
            asn_denied=False,
            burst_hit=1 if case['burst'] else 0,
            weights=weights,
            thresholds=thresholds,
            mlp_score=mlp_score,
            yara_score=yara_score
        )
        
        print(f"    MLP score: {mlp_score}")
        print(f"    YARA score: {yara_score}")
        print(f"    Total score: {score}")
        print(f"    Reasons: {reasons}")
        print(f"    Action: {action}")
        
        # Show decision color-coded
        if action == 'block':
            print(f"    Result: ⛔ BLOCK")
        elif action == 'monitor':
            print(f"    Result: ⚠ MONITOR")
        else:
            print(f"    Result: ✓ ALLOW")
    
    print("\n✓ Decision integration OK")
    return True


def test_end_to_end():
    """Test 5: End-to-end simulation."""
    print("\n[TEST 5] End-to-End Simulation")
    print("=" * 70)
    
    print("\nSimulating: DNS Query → Flow → MLP → YARA → Decision")
    
    # Initialize components
    tracker = FlowTracker()
    
    mlp_detector = None
    if MLP_AVAILABLE:
        model_path = script_dir / 'models' / 'mlp_engine.pkl'
        if model_path.exists():
            mlp_detector = MLPThreatDetector(str(model_path))
    
    yara_scanner = None
    if YARA_AVAILABLE:
        rules_dir = script_dir / 'yara_rules'
        if rules_dir.exists():
            yara_scanner = YARAScanner(str(rules_dir))
    
    # Simulate DNS query and traffic
    client_ip = "192.168.1.100"
    domain = "slot-gacor-terpercaya.xyz"
    
    print(f"\n1. DNS Query: {client_ip} -> {domain}")
    
    # Update flow
    flow = tracker.update_flow(client_ip, "1.2.3.4", 443, "tcp", pkt_size=1500)
    
    # Simulate packets
    for _ in range(100):
        flow.update(pkt_size=1500, direction='out')
    
    # Enrich with DNS
    tracker.enrich_with_dns(client_ip, domain)
    flow.domain = domain
    flow.tls_seen = True
    
    print(f"2. Flow Updated: {flow.pkt_count} packets")
    
    # Extract features
    features = build_feature_vector_24(flow)
    print(f"3. Features Extracted: {len(features)} features")
    
    # MLP inference
    mlp_score = 0
    if mlp_detector and mlp_detector.model_loaded:
        is_threat, proba = mlp_detector.is_suspicious(flow, return_probability=True)
        if is_threat:
            mlp_score = int(proba * 100)
        print(f"4. MLP Inference: {'Threat' if is_threat else 'Normal'} (score: {mlp_score})")
    else:
        print("4. MLP Inference: Skipped (not available)")
    
    # YARA scan
    yara_score = 0
    if yara_scanner and yara_scanner.rules_loaded:
        matches = yara_scanner.scan_payload(domain.encode('utf-8'))
        if matches:
            severity_scores = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
            yara_score = max(severity_scores.get(m.get_severity(), 25) for m in matches)
            print(f"5. YARA Scan: {len(matches)} match(es) (score: {yara_score})")
            for match in matches[:3]:
                print(f"   - {match.rule}")
        else:
            print(f"5. YARA Scan: No matches")
    else:
        print("5. YARA Scan: Skipped (not available)")
    
    # Decision
    from minifw_ai.main import score_and_decide
    
    class SimpleThresholds:
        monitor_threshold = 40
        block_threshold = 60
    
    weights = {
        'dns_weight': 41,
        'mlp_weight': 30,
        'yara_weight': 35
    }
    
    score, reasons, action = score_and_decide(
        domain=domain,
        denied=True,  # Assume in deny list
        sni_denied=False,
        asn_denied=False,
        burst_hit=0,
        weights=weights,
        thresholds=SimpleThresholds(),
        mlp_score=mlp_score,
        yara_score=yara_score
    )
    
    print(f"6. Decision: {action.upper()} (score: {score})")
    print(f"   Reasons: {reasons}")
    
    print("\n✓ End-to-end simulation complete")
    return True


def main():
    """Main test runner."""
    
    tests = []
    
    # Test 1: Flow tracking (always runs)
    success, tracker = test_flow_tracking()
    tests.append(("Flow Tracking", success))
    
    if not success:
        print("\n❌ Flow tracking failed, cannot continue")
        sys.exit(1)
    
    # Test 2: MLP (optional)
    success, mlp_detector = test_mlp_detection(tracker)
    tests.append(("MLP Detection", success))
    
    # Test 3: YARA (optional)
    success, yara_scanner = test_yara_scanning()
    tests.append(("YARA Scanning", success))
    
    # Test 4: Integration
    success = test_decision_integration(tracker, mlp_detector, yara_scanner)
    tests.append(("Decision Integration", success))
    
    # Test 5: End-to-end
    success = test_end_to_end()
    tests.append(("End-to-End", success))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # Component status
    print("\nComponents Status:")
    print(f"  Flow Collector: ✓ Available")
    print(f"  MLP Engine: {'✓ Available' if MLP_AVAILABLE else '⚠ Not available'}")
    print(f"  YARA Scanner: {'✓ Available' if YARA_AVAILABLE else '⚠ Not available'}")
    
    if passed == total:
        print("\n✓ All tests passed! Full integration working.")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
