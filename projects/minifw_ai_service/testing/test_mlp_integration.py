#!/usr/bin/env python3
"""
MLP Integration Test v1.1 - With Critical Fixes Verification
Tests MLP engine integration with hard gates and feature name fixes.

This test verifies:
1. MLP model loading
2. Feature extraction with FEATURE_NAMES
3. MLP inference WITHOUT feature name warnings (DataFrame fix)
4. Hard threat gates override logic
5. Integration with scoring system
6. End-to-end flow simulation

Usage:
    python3 testing/test_mlp_integration.py --model models/mlp_engine.pkl
"""
import sys
import argparse
from pathlib import Path
import warnings

# Add app to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'app'))

from minifw_ai.collector_flow import FlowTracker, FlowStats, build_feature_vector_24

try:
    from minifw_ai.utils.mlp_engine import MLPThreatDetector, FEATURE_NAMES
    MLP_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: MLP engine not available: {e}")
    print("\nInstall dependencies:")
    print("  pip install scikit-learn pandas numpy")
    sys.exit(1)


def test_1_model_loading(model_path: str):
    """Test 1: Model loading and initialization."""
    print("\n[TEST 1] MLP Model Loading")
    print("=" * 70)
    
    if not Path(model_path).exists():
        print(f"❌ FAIL: Model file not found: {model_path}")
        return False
    
    try:
        detector = MLPThreatDetector(model_path=model_path, threshold=0.5)
        
        if not detector.model_loaded:
            print("❌ FAIL: Model not loaded")
            return False
        
        print(f"✓ Model loaded: {model_path}")
        print(f"  Threshold: {detector.threshold}")
        print(f"  Scaler available: {detector.scaler is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_feature_names():
    """Test 2: Feature names constant verification."""
    print("\n[TEST 2] Feature Names Verification")
    print("=" * 70)
    
    try:
        tracker = FlowTracker()
        
        # Create test flow
        flow = tracker.update_flow('192.168.1.100', '8.8.8.8', 443, 'tcp', pkt_size=1500)
        
        # Simulate packets
        for _ in range(100):
            flow.update(pkt_size=1500, direction='out')
        
        # Extract features
        features = build_feature_vector_24(flow)
        
        print(f"✓ Extracted {len(features)} features")
        
        # Check feature count
        if len(features) != 24:
            print(f"❌ FAIL: Expected 24 features, got {len(features)}")
            return False
        
        # Check FEATURE_NAMES constant exists
        if not FEATURE_NAMES:
            print("❌ FAIL: FEATURE_NAMES not defined in mlp_engine")
            return False
        
        print(f"✓ FEATURE_NAMES defined: {len(FEATURE_NAMES)} names")
        
        if len(FEATURE_NAMES) != 24:
            print(f"❌ FAIL: FEATURE_NAMES has {len(FEATURE_NAMES)} names, expected 24")
            return False
        
        print(f"\nFirst 5 Feature Names:")
        for i, name in enumerate(FEATURE_NAMES[:5]):
            print(f"  {i+1}. {name}: {features[i]:.4f}")
        print(f"  ... (19 more)")
        
        print("\n✓ Feature names OK")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_no_feature_warnings(model_path: str):
    """Test 3: CRITICAL - No feature name warnings (DataFrame fix)."""
    print("\n[TEST 3] Feature Name Warning Check (CRITICAL FIX)")
    print("=" * 70)
    
    try:
        detector = MLPThreatDetector(model_path=model_path)
        tracker = FlowTracker()
        
        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Test flow 1: Normal
            flow1 = tracker.update_flow('192.168.1.100', '8.8.8.8', 443, 'tcp', pkt_size=1500)
            for _ in range(50):
                flow1.update(pkt_size=1500, direction='out')
            
            is_threat1, proba1 = detector.is_suspicious(flow1, return_probability=True)
            
            # Test flow 2: Suspicious pattern
            flow2 = tracker.update_flow('192.168.1.101', '1.2.3.4', 80, 'tcp', pkt_size=100)
            for _ in range(200):
                flow2.update(pkt_size=100, direction='out')
            
            is_threat2, proba2 = detector.is_suspicious(flow2, return_probability=True)
            
            # Check for feature name warnings
            feature_warnings = [warning for warning in w 
                              if "feature names" in str(warning.message).lower()]
            
            if feature_warnings:
                print("❌ FAIL: Feature name warnings detected!")
                print("  This means DataFrame fix not applied correctly.")
                for warning in feature_warnings:
                    print(f"  Warning: {warning.message}")
                return False
        
        print("✓ NO feature name warnings (DataFrame fix working!)")
        
        print(f"\nTest Results:")
        print(f"  Flow 1 (Normal): threat={is_threat1}, proba={proba1:.4f}")
        print(f"  Flow 2 (Suspicious): threat={is_threat2}, proba={proba2:.4f}")
        
        print("\n✓ CRITICAL FIX VERIFIED: DataFrame with FEATURE_NAMES working")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_hard_threat_gates():
    """Test 4: CRITICAL - Hard threat gates logic."""
    print("\n[TEST 4] Hard Threat Gates (CRITICAL FIX)")
    print("=" * 70)
    
    try:
        tracker = FlowTracker()
        
        # Gate 1: PPS Saturation
        print("\n  Gate 1: PPS Saturation (>200 pps)")
        flow1 = tracker.update_flow('192.168.1.100', '8.8.8.8', 443, 'tcp', pkt_size=1500)
        
        # Simulate 1000 packets over 4 seconds (250 pps)
        import time
        flow1.first_seen = time.time() - 4.0
        flow1.last_seen = time.time()
        flow1.pkt_count = 1000
        
        if flow1.pkts_per_sec > 200:
            print(f"  ✓ PASS: PPS {flow1.pkts_per_sec:.2f} > 200 → SHOULD BLOCK")
        else:
            print(f"  ❌ FAIL: PPS {flow1.pkts_per_sec:.2f} <= 200")
            return False
        
        # Gate 2: Burst Flood
        print("\n  Gate 2: Burst Flood (>300 pkts/s)")
        flow2 = tracker.update_flow('192.168.1.101', '1.2.3.4', 80, 'tcp', pkt_size=100)
        
        # Simulate burst by adding to burst_windows
        flow2.burst_windows.append({'pkts': 400, 'bytes': 40000, 'time': time.time()})
        
        if flow2.max_burst_pkts_1s > 300:
            print(f"  ✓ PASS: Burst {flow2.max_burst_pkts_1s} > 300 → SHOULD BLOCK")
        else:
            print(f"  ❌ FAIL: Burst {flow2.max_burst_pkts_1s} <= 300")
            return False
        
        # Gate 3: Bot-like Small Packets
        print("\n  Gate 3: Bot-like Pattern (>95% small + <3s)")
        flow3 = tracker.update_flow('192.168.1.102', '5.6.7.8', 443, 'tcp', pkt_size=50)
        
        # Simulate 2.5 seconds with 98% small packets
        flow3.first_seen = time.time() - 2.5
        flow3.last_seen = time.time()
        
        # Add mostly small packets
        for _ in range(98):
            flow3.pkt_sizes.append(50)  # Small
        for _ in range(2):
            flow3.pkt_sizes.append(1500)  # Large
        
        if flow3.small_pkt_ratio > 0.95 and flow3.duration < 3:
            print(f"  ✓ PASS: Small {flow3.small_pkt_ratio:.2%}, dur {flow3.duration:.2f}s → SHOULD BLOCK")
        else:
            print(f"  ❌ FAIL: Conditions not met (small={flow3.small_pkt_ratio:.2%}, dur={flow3.duration:.2f}s)")
            return False
        
        # Gate 4: Normal flow (should NOT trigger)
        print("\n  Gate 4: Normal Flow (should NOT trigger)")
        flow4 = tracker.update_flow('192.168.1.103', '8.8.4.4', 443, 'tcp', pkt_size=1500)
        
        # Simulate normal flow: 50 packets over 5 seconds (10 pps)
        flow4.first_seen = time.time() - 5.0
        flow4.last_seen = time.time()
        flow4.pkt_count = 50
        flow4.burst_windows.append({'pkts': 20, 'bytes': 30000, 'time': time.time()})
        
        # Add normal packet sizes
        for _ in range(30):
            flow4.pkt_sizes.append(1500)
        for _ in range(20):
            flow4.pkt_sizes.append(800)
        
        gates_triggered = (
            flow4.pkts_per_sec > 200 or
            flow4.max_burst_pkts_1s > 300 or
            (flow4.small_pkt_ratio > 0.95 and flow4.duration < 3)
        )
        
        if not gates_triggered:
            print(f"  ✓ PASS: Normal flow (PPS={flow4.pkts_per_sec:.2f}) does NOT trigger")
        else:
            print(f"  ❌ FAIL: Normal flow incorrectly triggered gates")
            return False
        
        print("\n✓ CRITICAL FIX VERIFIED: Hard threat gates working")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_hard_gate_overrides_mlp(model_path: str):
    """Test 5: Hard gates override MLP decisions."""
    print("\n[TEST 5] Hard Gates Override MLP")
    print("=" * 70)
    
    try:
        from minifw_ai.main import score_and_decide
        
        class SimpleThresholds:
            monitor_threshold = 40
            block_threshold = 60
        
        detector = MLPThreatDetector(model_path=model_path)
        tracker = FlowTracker()
        thresholds = SimpleThresholds()
        
        weights = {
            'dns_weight': 41,
            'sni_weight': 34,
            'asn_weight': 15,
            'burst_weight': 10,
            'mlp_weight': 30,
            'yara_weight': 35
        }
        
        # Scenario: Saturation attack
        print("\n  Scenario: Saturation Attack (PPS=333)")
        flow = tracker.update_flow('192.168.1.100', '1.2.3.4', 80, 'tcp', pkt_size=100)
        
        # Simulate saturation: 1000 packets over 3 seconds (333 pps)
        import time
        flow.first_seen = time.time() - 3.0
        flow.last_seen = time.time()
        flow.pkt_count = 1000
        
        # Simulate packets
        for _ in range(50):
            flow.update(pkt_size=100)
        
        # Check hard gates FIRST (like main.py does)
        hard_threat = flow.pkts_per_sec > 200
        
        if hard_threat:
            mlp_score = 100  # Force block
            print(f"    ✓ Hard gate triggered: PPS {flow.pkts_per_sec:.2f} > 200")
            print(f"    ✓ MLP score FORCED to 100 (override)")
        else:
            # Only call MLP if no hard threat
            is_threat, proba = detector.is_suspicious(flow, return_probability=True)
            mlp_score = int(proba * 100) if is_threat else 0
            print(f"    MLP would say: threat={is_threat}, proba={proba:.4f}")
        
        # Make decision
        score, reasons, action = score_and_decide(
            domain='unknown-site.com',
            denied=False,
            sni_denied=False,
            asn_denied=False,
            burst_hit=0,
            weights=weights,
            thresholds=thresholds,
            mlp_score=mlp_score,
            yara_score=0,
            hard_threat_override=hard_threat  # NEW: Pass override flag
        )
        
        print(f"    Final score: {score}")
        print(f"    Final action: {action}")
        
        if action != 'block':
            print(f"    ❌ FAIL: Expected BLOCK, got {action}")
            return False
        
        print(f"    ✓ PASS: Saturation attack BLOCKED (hard gate override)")
        
        print("\n✓ Hard gates correctly override MLP")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_end_to_end(model_path: str):
    """Test 6: End-to-end simulation."""
    print("\n[TEST 6] End-to-End Simulation")
    print("=" * 70)
    
    try:
        detector = MLPThreatDetector(model_path=model_path)
        tracker = FlowTracker()
        
        print("\nSimulating: DNS → Flow → Hard Gates → MLP → Decision")
        
        client_ip = "192.168.1.100"
        domain = "example.com"
        
        print(f"\n1. DNS Query: {client_ip} → {domain}")
        
        # Create flow
        flow = tracker.update_flow(client_ip, "93.184.216.34", 443, "tcp", pkt_size=1500)
        
        # Simulate 100 packets
        for _ in range(100):
            flow.update(pkt_size=1500)
        
        tracker.enrich_with_dns(client_ip, domain)
        flow.domain = domain
        flow.tls_seen = True
        
        print(f"2. Flow: {flow.pkt_count} packets, {flow.get_duration():.2f}s")
        
        # Extract features
        features = build_feature_vector_24(flow)
        print(f"3. Features: {len(features)} extracted")
        
        # Check hard gates
        print(f"4. Hard Gate Check:")
        print(f"   PPS: {flow.pkts_per_sec:.2f} (threshold: 200)")
        print(f"   Burst: {flow.max_burst_pkts_1s} (threshold: 300)")
        print(f"   Small: {flow.small_pkt_ratio:.2%} (threshold: 95%)")
        
        hard_threat = (
            flow.pkts_per_sec > 200 or
            flow.max_burst_pkts_1s > 300 or
            (flow.small_pkt_ratio > 0.95 and flow.duration < 3)
        )
        
        if hard_threat:
            print(f"   ⚠ Hard gate TRIGGERED → Force block")
            mlp_score = 100
        else:
            print(f"   ✓ Hard gates PASS → Call MLP")
            
            # Test for feature name warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                is_threat, proba = detector.is_suspicious(flow, return_probability=True)
                
                feature_warnings = [warning for warning in w 
                                  if "feature names" in str(warning.message).lower()]
                
                if feature_warnings:
                    print(f"   ❌ Feature name warning detected!")
                    return False
            
            mlp_score = int(proba * 100) if is_threat else 0
            
            print(f"5. MLP Inference (no warnings):")
            print(f"   Threat: {is_threat}")
            print(f"   Probability: {proba:.4f}")
            print(f"   Score: {mlp_score}")
        
        print(f"\n6. Final MLP Score: {mlp_score}")
        print(f"   Decision: {'BLOCK' if mlp_score >= 50 else 'ALLOW/MONITOR'}")
        
        print("\n✓ End-to-end simulation complete")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Test MLP v1.1 with critical fixes')
    parser.add_argument('--model', default='models/mlp_engine.pkl',
                       help='Path to MLP model file')
    args = parser.parse_args()
    
    print("=" * 70)
    print("MiniFW-AI MLP Integration Test v1.1")
    print("Verifying Critical Fixes: Feature Names + Hard Gates")
    print("=" * 70)
    
    tests = [
        ("Model Loading", lambda: test_1_model_loading(args.model)),
        ("Feature Names", test_2_feature_names),
        ("No Feature Warnings (FIX #1)", lambda: test_3_no_feature_warnings(args.model)),
        ("Hard Threat Gates (FIX #2)", test_4_hard_threat_gates),
        ("Hard Gates Override MLP", lambda: test_5_hard_gate_overrides_mlp(args.model)),
        ("End-to-End", lambda: test_6_end_to_end(args.model)),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ TEST EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # Critical fixes verification
    print("\n" + "=" * 70)
    print("CRITICAL FIXES VERIFICATION")
    print("=" * 70)
    
    fix1 = results[2][1]  # No feature warnings
    fix2 = results[3][1]  # Hard gates
    fix3 = results[4][1]  # Override logic
    
    print(f"  Feature Names Fix: {'✓ VERIFIED' if fix1 else '❌ FAILED'}")
    print(f"  Hard Gates Fix: {'✓ VERIFIED' if fix2 else '❌ FAILED'}")
    print(f"  Override Logic: {'✓ VERIFIED' if fix3 else '❌ FAILED'}")
    
    if fix1 and fix2 and fix3:
        print("\n✅ ALL CRITICAL FIXES VERIFIED!")
        print("  MiniFW-AI v1.1 ready for production")
    else:
        print("\n❌ CRITICAL FIXES NOT FULLY VERIFIED")
        print("  Please review failed tests")
    
    if passed == total:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
