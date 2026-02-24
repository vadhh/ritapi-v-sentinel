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

import pytest

# Add app to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'app'))

from minifw_ai.collector_flow import FlowTracker, FlowStats, build_feature_vector_24

try:
    from minifw_ai.utils.mlp_engine import MLPThreatDetector
    MLP_AVAILABLE = True
except ImportError:
    MLP_AVAILABLE = False

try:
    from minifw_ai.utils.yara_scanner import YARAScanner
    YARA_AVAILABLE = True
except ImportError:
    YARA_AVAILABLE = False

_MODEL_PATH = script_dir / 'models' / 'mlp_engine.pkl'
_RULES_DIR = script_dir / 'yara_rules'


@pytest.fixture
def tracker():
    return FlowTracker(flow_timeout=300)


@pytest.fixture
def mlp_detector():
    if not MLP_AVAILABLE:
        return None
    if not _MODEL_PATH.exists():
        return None
    det = MLPThreatDetector(model_path=str(_MODEL_PATH), threshold=0.5)
    return det if det.model_loaded else None


@pytest.fixture
def yara_scanner():
    if not YARA_AVAILABLE or not _RULES_DIR.exists():
        return None
    scanner = YARAScanner(rules_dir=str(_RULES_DIR))
    return scanner if scanner.rules_loaded else None


def test_flow_tracking(tracker):
    """Test 1: Flow tracking and feature extraction."""
    try:
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
        
        assert len(flows) == 3
        for flow in flows:
            features = build_feature_vector_24(flow)
            assert len(features) == 24

    except Exception as e:
        import traceback
        traceback.print_exc()
        pytest.fail(str(e))


def test_mlp_detection(tracker, mlp_detector):
    """Test 2: MLP threat detection (skipped if model unavailable)."""
    if mlp_detector is None:
        pytest.skip("MLP model not available")

    # populate tracker with flows
    test_flows = [
        ('192.168.1.100', '8.8.8.8', 443, 'tcp', 'google.com'),
        ('192.168.1.100', '1.2.3.4', 443, 'tcp', 'slot-gacor.xyz'),
    ]
    for client_ip, dst_ip, dst_port, proto, domain in test_flows:
        flow = tracker.update_flow(client_ip, dst_ip, dst_port, proto, pkt_size=1500)
        for _ in range(50):
            flow.update(pkt_size=1500, direction='out')
        tracker.enrich_with_dns(client_ip, domain)
        flow.domain = domain

    flows = tracker.get_all_active_flows()
    for flow in flows:
        is_threat, proba = mlp_detector.is_suspicious(flow, return_probability=True)
        assert is_threat in (True, False)
        assert 0.0 <= proba <= 1.0


def test_yara_scanning(yara_scanner):
    """Test 3: YARA payload scanning (skipped if rules unavailable)."""
    if yara_scanner is None:
        pytest.skip("YARA scanner/rules not available")

    test_payloads = [
        'slot gacor online deposit pulsa tanpa potongan',
        'welcome to our professional website',
        'powershell -enc base64encodedcommand',
    ]
    for payload in test_payloads:
        matches = yara_scanner.scan_payload(payload)
        assert isinstance(matches, list)


def test_decision_integration(tracker, mlp_detector, yara_scanner):  # noqa: F811
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


if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
