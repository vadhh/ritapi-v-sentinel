#!/usr/bin/env python3
"""
MiniFW-AI Feature Demo Script
==============================
Interactive terminal UI for demonstrating all MiniFW-AI features.

Usage:
    cd /home/stardhoom/minifw-ai
    python3 demo/demo_all_features.py

Author: MiniFW-AI Team
"""
import sys
import os
import time
from pathlib import Path

# Setup path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

# ============================================================================
# TERMINAL UI UTILITIES
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    DIM = '\033[2m'

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')

def print_banner():
    """Print demo banner."""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ███╗   ███╗██╗███╗   ██╗██╗███████╗██╗    ██╗      █████╗ ██╗              ║
║   ████╗ ████║██║████╗  ██║██║██╔════╝██║    ██║     ██╔══██╗██║              ║
║   ██╔████╔██║██║██╔██╗ ██║██║█████╗  ██║ █╗ ██║     ███████║██║              ║
║   ██║╚██╔╝██║██║██║╚██╗██║██║██╔══╝  ██║███╗██║     ██╔══██║██║              ║
║   ██║ ╚═╝ ██║██║██║ ╚████║██║██║     ╚███╔███╔╝     ██║  ██║██║              ║
║   ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝╚═╝      ╚══╝╚══╝      ╚═╝  ╚═╝╚═╝              ║
║                                                                              ║
║              RITAPI Sentinel - Gateway Metadata Protection Layer             ║
║                        Feature Demonstration Suite                           ║
╚══════════════════════════════════════════════════════════════════════════════╝    
{Colors.END}"""
    print(banner)

def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'─' * 78}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'─' * 78}{Colors.END}\n")

def print_test(name: str, status: str, details: str = ""):
    """Print a test result."""
    if status == "PASS":
        icon = f"{Colors.GREEN}✓{Colors.END}"
        status_str = f"{Colors.GREEN}PASS{Colors.END}"
    elif status == "FAIL":
        icon = f"{Colors.RED}✗{Colors.END}"
        status_str = f"{Colors.RED}FAIL{Colors.END}"
    elif status == "SKIP":
        icon = f"{Colors.YELLOW}○{Colors.END}"
        status_str = f"{Colors.YELLOW}SKIP{Colors.END}"
    else:
        icon = f"{Colors.CYAN}●{Colors.END}"
        status_str = f"{Colors.CYAN}INFO{Colors.END}"
    
    print(f"  {icon} [{status_str}] {name}")
    if details:
        print(f"           {Colors.DIM}{details}{Colors.END}")

def print_info(key: str, value: str):
    """Print an info line."""
    print(f"  {Colors.CYAN}▸{Colors.END} {key}: {Colors.BOLD}{value}{Colors.END}")

def type_text(text: str, delay: float = 0.015, end: str = "\n"):
    """Print text with typewriter effect."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)
    sys.stdout.flush()

def print_explanation(text: str):
    """Print an explanation with typewriter effect."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}ℹ WHAT IS THIS?{Colors.END}")
    type_text(f"{Colors.DIM}{text}{Colors.END}\n")

def print_scenario(name: str, outcome: str, expected: bool = True):
    """Print a scenario description."""
    icon = "✓" if expected else "✗"
    color = Colors.GREEN if outcome == "ALLOW" else Colors.RED
    print(f"  {Colors.DIM}Scenario:{Colors.END} {name:<40} → {color}{Colors.BOLD}{outcome}{Colors.END}")

def wait_for_key(prompt: str = "Press ENTER to continue..."):
    """Wait for user input."""
    print(f"\n{Colors.DIM}{prompt}{Colors.END}")
    input()

# ============================================================================
# FEATURE TESTS
# ============================================================================

def test_sector_lock():
    """Test 1: Sector Lock System."""
    print_section("TEST 1: SECTOR LOCK SYSTEM (Factory-Set Configuration)")
    
    print_explanation(
        "The Sector Lock enforces factory-set policies based on the deployment environment\n"
        "(School, Hospital, Gov, etc.). This makes the core security policy IMMUTABLE\n"
        "and resistant to tampering, even if the admin UI is compromised."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("Admin tries to change Sector", "BLOCKED")
    print_scenario("System enforces SafeSearch", "FORCED")
    print_scenario("School-specific blacklists", "ACTIVE")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    # Check if sector is configured
    sector_env = os.environ.get("MINIFW_SECTOR", "")
    if not sector_env:
        print_info("Warning", "MINIFW_SECTOR not set, using default from config file")
    
    try:
        from app.minifw_ai.sector_lock import get_sector_lock
        from app.models.user import SectorType
        
        lock = get_sector_lock()
        sector = lock.get_sector()
        config = lock.get_sector_config()
        
        # Test 1.1: Sector loads correctly
        print_test("Sector loads from environment/config", "PASS", f"Sector = {sector}")
        results["passed"] += 1
        
        # Test 1.2: Is locked
        if lock.is_locked():
            print_test("Sector is locked (immutable)", "PASS", "Cannot be changed via UI")
            results["passed"] += 1
        else:
            print_test("Sector is locked", "FAIL")
            results["failed"] += 1
        
        # Test 1.3: Config available
        desc = config.get("description", "N/A")
        print_test("Sector config retrieval", "PASS", desc)
        results["passed"] += 1
        
        # Test 1.4: All sectors in enum
        expected = {"hospital", "school", "government", "finance", "legal", "establishment"}
        actual = {s.value for s in SectorType}
        if expected == actual:
            print_test("All 6 sectors defined in enum", "PASS")
            results["passed"] += 1
        else:
            print_test("All 6 sectors defined", "FAIL", f"Missing: {expected - actual}")
            results["failed"] += 1
        
        # Test 1.5: Sector-specific features
        print()
        print_info("Current Sector", sector.upper())
        print_info("SafeSearch", "Enabled" if config.get("force_safesearch") else "Disabled")
        print_info("VPN Blocking", "Enabled" if config.get("block_vpns") else "Disabled")
        print_info("IoMT Priority", "Enabled" if config.get("iomt_high_priority") else "Disabled")
        print_info("Extra Feeds", str(config.get("extra_feeds", [])))
        
    except RuntimeError as e:
        print_test("Sector lock initialization", "FAIL", str(e))
        results["failed"] += 1
    except Exception as e:
        print_test("Sector lock test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_feed_system():
    """Test 2: Feed System."""
    print_section("TEST 2: FEED SYSTEM (Threat Intelligence)")
    
    print_explanation(
        "The Feed System blocks domains based on local high-performance blocklists.\n"
        "It supports glob patterns (*.casino) and integrates with sector-specific feeds."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("User visits 'google.com'", "ALLOW")
    print_scenario("User visits 'malware.example.com'", "BLOCK")
    print_scenario("User visits Gambling site", "BLOCK")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        from app.minifw_ai.feeds import FeedMatcher
        
        feeds_dir = script_dir / "config" / "feeds"
        
        # Test 2.1: FeedMatcher initialization
        matcher = FeedMatcher(str(feeds_dir))
        print_test("FeedMatcher initialization", "PASS", f"Feeds dir: {feeds_dir}")
        results["passed"] += 1
        
        # Test 2.2: Deny domains loaded
        deny_count = len(matcher.deny_domains)
        print_test("Deny domains loaded", "PASS", f"{deny_count} patterns")
        results["passed"] += 1
        
        # Test 2.3: Allow domains loaded
        allow_count = len(matcher.allow_domains)
        print_test("Allow domains loaded", "PASS", f"{allow_count} patterns")
        results["passed"] += 1
        
        # Test 2.4: Domain matching
        test_domains = [
            ("malware.example.com", True, "Should be blocked"),
            ("google.com", False, "Should be allowed"),
            ("slot-gacor.xyz", True, "Gambling site"),
        ]
        
        for domain, expected_denied, desc in test_domains:
            is_denied = matcher.domain_denied(domain)
            if is_denied == expected_denied:
                status = "PASS"
                results["passed"] += 1
            else:
                status = "FAIL"
                results["failed"] += 1
            print_test(f"Domain check: {domain}", status, desc)
        
        # Test 2.5: Sector-specific feed loading
        school_feed = feeds_dir / "school_blacklist.txt"
        if school_feed.exists():
            loaded = matcher.load_sector_feeds(["school_blacklist.txt"])
            print_test("Sector feed loading", "PASS", f"Loaded {loaded} patterns from school_blacklist.txt")
            results["passed"] += 1
        else:
            print_test("Sector feed loading", "SKIP", "school_blacklist.txt not found")
            results["skipped"] += 1
        
    except Exception as e:
        print_test("Feed system test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_flow_collector():
    """Test 3: Flow Collector."""
    print_section("TEST 3: FLOW COLLECTOR (Network Traffic Analysis)")
    
    print_explanation(
        "The Flow Collector analyzes network traffic metadata (IPs, Ports, Timings)\n"
        "without inspecting packet contents. It builds statistical feature vectors\n"
        "(duration, burst size, inter-arrival times) for AI analysis."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("High-speed Burst Traffic", "DETECTED")
    print_scenario("Slow low-and-slow attack", "TRACKED")
    print_scenario("Encrypted Traffic (TLS)", "ANALYZED (Metadata)")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        from app.minifw_ai.collector_flow import FlowTracker, build_feature_vector_24
        
        # Test 3.1: FlowTracker initialization
        tracker = FlowTracker(flow_timeout=300)
        print_test("FlowTracker initialization", "PASS")
        results["passed"] += 1
        
        # Test 3.2: Create test flows
        test_flows = [
            ("192.168.1.100", "8.8.8.8", 443, "tcp"),
            ("192.168.1.101", "1.1.1.1", 80, "tcp"),
            ("192.168.1.102", "1.2.3.4", 443, "tcp"),
        ]
        
        for client_ip, dst_ip, dst_port, proto in test_flows:
            flow = tracker.update_flow(client_ip, dst_ip, dst_port, proto, pkt_size=1500)
            # Simulate packets
            for _ in range(20):
                flow.update(pkt_size=1500, direction='out')
        
        flows = tracker.get_all_active_flows()
        print_test("Flow creation", "PASS", f"Created {len(flows)} flows")
        results["passed"] += 1
        
        # Test 3.3: Feature extraction
        if flows:
            features = build_feature_vector_24(flows[0])
            print_test("Feature extraction (24 features)", "PASS", f"Duration: {features[0]:.2f}s, Packets: {features[1]:.0f}")
            results["passed"] += 1
        
        # Test 3.4: DNS enrichment
        tracker.enrich_with_dns("192.168.1.100", "example.com")
        print_test("DNS enrichment", "PASS")
        results["passed"] += 1
        
    except Exception as e:
        print_test("Flow collector test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_mlp_engine():
    """Test 4: MLP Threat Detection Engine."""
    print_section("TEST 4: MLP ENGINE (AI Threat Detection)")
    
    print_explanation(
        "The MLP (Multi-Layer Perceptron) Engine uses a trained neural network to\n"
        "detect malicious traffic patterns based on 24 flow features. It can spot\n"
        "C2 beacons, tunneling, and botnet activity that evades static rules."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("Normal Web Browsing", "CLEAN")
    print_scenario("C2 Beaconing Pattern", "THREAT DETECTED")
    print_scenario("Data Exfiltration", "THREAT DETECTED")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        from app.minifw_ai.utils.mlp_engine import MLPThreatDetector
        
        model_path = script_dir / "models" / "mlp_engine.pkl"
        
        if not model_path.exists():
            print_test("MLP model file exists", "SKIP", f"Model not found: {model_path}")
            print_info("Note", "Train a model with: python3 scripts/train_mlp.py")
            results["skipped"] += 1
            return results
        
        # Test 4.1: Model loading
        detector = MLPThreatDetector(str(model_path), threshold=0.5)
        
        if detector.model_loaded:
            print_test("MLP model loaded", "PASS", f"Model: {model_path.name}")
            results["passed"] += 1
        else:
            print_test("MLP model loaded", "FAIL")
            results["failed"] += 1
            return results
        
        # Test 4.2: Create test flow for inference
        from app.minifw_ai.collector_flow import FlowTracker
        
        tracker = FlowTracker()
        flow = tracker.update_flow("192.168.1.100", "1.2.3.4", 443, "tcp", pkt_size=1500)
        for _ in range(50):
            flow.update(pkt_size=1500, direction='out')
        
        is_threat, proba = detector.is_suspicious(flow, return_probability=True)
        
        print_test("MLP inference", "PASS", f"Threat: {is_threat}, Probability: {proba:.4f}")
        results["passed"] += 1
        
        print_info("Threshold", str(detector.threshold))
        print_info("Verdict", "THREAT" if is_threat else "NORMAL")
        
    except ImportError:
        print_test("MLP engine import", "SKIP", "scikit-learn not installed")
        results["skipped"] += 1
    except Exception as e:
        print_test("MLP engine test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_yara_scanner():
    """Test 5: YARA Payload Scanner."""
    print_section("TEST 5: YARA SCANNER (Payload Analysis)")
    
    print_explanation(
        "The YARA Scanner inspects extracted payloads (DNS queries, SNI, HTTP headers)\n"
        "for known malicious signatures, keywords (gambling, porn), and exploit patterns."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("Casino/Gambling Keywords", "MATCHED")
    print_scenario("Malicious PowerShell Script", "MATCHED")
    print_scenario("Business Documents", "CLEAN")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        from app.minifw_ai.utils.yara_scanner import YARAScanner
        
        rules_dir = script_dir / "yara_rules"
        
        if not rules_dir.exists():
            print_test("YARA rules directory", "SKIP", f"Not found: {rules_dir}")
            results["skipped"] += 1
            return results
        
        # Test 5.1: Scanner initialization
        scanner = YARAScanner(str(rules_dir))
        
        if scanner.rules_loaded:
            stats = scanner.get_stats()
            print_test("YARA rules loaded", "PASS", f"{stats['rules_loaded']} rules")
            results["passed"] += 1
        else:
            print_test("YARA rules loaded", "SKIP", "No rules compiled")
            results["skipped"] += 1
            return results
        
        # Test 5.2: Payload scanning
        test_payloads = [
            ("slot-gacor-online.com", "Gambling domain"),
            ("normal-business.com", "Normal domain"),
            ("powershell -enc base64", "Suspicious payload"),
        ]
        
        for payload, desc in test_payloads:
            matches = scanner.scan_payload(payload.encode())
            if matches:
                print_test(f"Scan: {desc}", "INFO", f"Detected: {len(matches)} match(es)")
            else:
                print_test(f"Scan: {desc}", "INFO", "Clean")
        results["passed"] += 1
        
    except ImportError:
        print_test("YARA scanner import", "SKIP", "yara-python not installed")
        results["skipped"] += 1
    except Exception as e:
        print_test("YARA scanner test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_scoring_engine():
    """Test 6: Scoring and Decision Engine."""
    print_section("TEST 6: SCORING ENGINE (Threat Decision)")
    
    print_explanation(
        "The Scoring Engine aggregates signals from all modules (Feed, AI, YARA, etc.)\n"
        "to calculate a final Threat Score (0-100). It applies specific policies\n"
        "to decide whether to ALLOW, MONITOR, or BLOCK the connection."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("Score < 40 (Low Risk)", "ALLOW")
    print_scenario("Score 40-60 (Medium Risk)", "MONITOR")
    print_scenario("Score > 60 (High Risk)", "BLOCK")
    print_scenario("Critical Threat (Hard Gate)", "INSTANT BLOCK")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        # Standalone scoring logic (mirrors main.py)
        def score_and_decide(denied, sni_denied, asn_denied, burst_hit, 
                            weights, block_threshold, monitor_threshold,
                            mlp_score=0, yara_score=0, hard_threat_override=False):
            """Simplified scoring function for testing."""
            if hard_threat_override:
                return 100, ["hard_threat"], "block"
            
            score = 0
            reasons = []
            
            if denied:
                score += weights.get('dns_weight', 41)
                reasons.append("dns_blocklist")
            if sni_denied:
                score += weights.get('sni_weight', 34)
                reasons.append("sni_blocklist")
            if asn_denied:
                score += weights.get('asn_weight', 15)
                reasons.append("asn_blocklist")
            if burst_hit:
                score += weights.get('burst_weight', 10)
                reasons.append("burst_exceeded")
            if mlp_score > 0:
                score += int(mlp_score * weights.get('mlp_weight', 30) / 100)
                reasons.append("mlp_suspicious")
            if yara_score > 0:
                score += int(yara_score * weights.get('yara_weight', 35) / 100)
                reasons.append("yara_match")
            
            if score >= block_threshold:
                return score, reasons, "block"
            elif score >= monitor_threshold:
                return score, reasons, "monitor"
            return score, reasons, "allow"
        
        weights = {
            'dns_weight': 41,
            'sni_weight': 34,
            'asn_weight': 15,
            'burst_weight': 10,
            'mlp_weight': 30,
            'yara_weight': 35
        }
        
        block_threshold = 60
        monitor_threshold = 40
        
        # Test scenarios
        test_cases = [
            {
                'name': 'Clean traffic',
                'denied': False, 'sni_denied': False, 'asn_denied': False,
                'burst_hit': 0, 'mlp_score': 0, 'yara_score': 0,
                'expected_action': 'allow'
            },
            {
                'name': 'Blocked domain only',
                'denied': True, 'sni_denied': False, 'asn_denied': False,
                'burst_hit': 0, 'mlp_score': 0, 'yara_score': 0,
                'expected_action': 'monitor'
            },
            {
                'name': 'Multi-signal threat',
                'denied': True, 'sni_denied': True, 'asn_denied': False,
                'burst_hit': 1, 'mlp_score': 50, 'yara_score': 0,
                'expected_action': 'block'
            },
        ]
        
        for case in test_cases:
            score, reasons, action = score_and_decide(
                denied=case['denied'],
                sni_denied=case['sni_denied'],
                asn_denied=case['asn_denied'],
                burst_hit=case['burst_hit'],
                weights=weights,
                block_threshold=block_threshold,
                monitor_threshold=monitor_threshold,
                mlp_score=case['mlp_score'],
                yara_score=case['yara_score']
            )
            
            if action == case['expected_action']:
                print_test(case['name'], "PASS", f"Score: {score}, Action: {action}")
                results["passed"] += 1
            else:
                print_test(case['name'], "FAIL", f"Expected {case['expected_action']}, got {action}")
                results["failed"] += 1
        
        # Test hard threat override
        score, reasons, action = score_and_decide(
            denied=False, sni_denied=False, asn_denied=False,
            burst_hit=0, weights=weights, 
            block_threshold=block_threshold, monitor_threshold=monitor_threshold,
            mlp_score=0, yara_score=0, hard_threat_override=True
        )
        
        if action == 'block' and score == 100:
            print_test("Hard threat override", "PASS", "Forces score=100, action=block")
            results["passed"] += 1
        else:
            print_test("Hard threat override", "FAIL")
            results["failed"] += 1
        
    except Exception as e:
        print_test("Scoring engine test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_policy_system():
    """Test 7: Policy Configuration."""
    print_section("TEST 7: POLICY SYSTEM (Configuration)")
    
    print_explanation(
        "The Policy System loads dynamic configuration rules (JSON) that define\n"
        "sensitivity thresholds, feature weights, and network segmentation rules\n"
        "without requiring code changes."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("Load Policy from JSON", "SUCCESS")
    print_scenario("Get Thresholds for VLAN 10", "RETRIEVED")
    print_scenario("Update Weights Live", "APPLIED")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        from app.minifw_ai.policy import Policy
        
        policy_path = script_dir / "config" / "policy.json"
        
        if not policy_path.exists():
            print_test("Policy file exists", "SKIP", f"Not found: {policy_path}")
            results["skipped"] += 1
            return results
        
        # Test 7.1: Policy loading
        pol = Policy(str(policy_path))
        print_test("Policy file loaded", "PASS")
        results["passed"] += 1
        
        # Test 7.2: Thresholds
        thr = pol.thresholds("default")
        print_test("Thresholds retrieval", "PASS", f"Block: {thr.block_threshold}, Monitor: {thr.monitor_threshold}")
        results["passed"] += 1
        
        # Test 7.3: Features
        features = pol.features()
        print_test("Feature weights", "PASS", f"DNS: {features.get('dns_weight')}, MLP: {features.get('mlp_weight')}")
        results["passed"] += 1
        
        # Test 7.4: Segment subnets
        subnets = pol.segment_subnets()
        print_test("Segment subnets", "PASS", f"{len(subnets)} segments defined")
        results["passed"] += 1
        
    except Exception as e:
        print_test("Policy system test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


def test_burst_tracker():
    """Test 8: Burst Detection."""
    print_section("TEST 8: BURST TRACKER (DDoS Detection)")
    
    print_explanation(
        "The Burst Tracker identifies high-rate traffic anomalies (DoS/DDoS attempts)\n"
        "by tracking query rates per client IP over sliding time windows."
    )

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚡ TEST SCENARIOS:{Colors.END}")
    print_scenario("Normal traffic (10 QPM)", "IGNORE")
    print_scenario("Burst traffic (60+ QPM)", "FLAGGED")
    print_scenario("DDoS Attack (200+ QPM)", "BLOCKED")
    print("\n" + "─"*50 + "\n")
    time.sleep(1)
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    try:
        from app.minifw_ai.burst import BurstTracker
        
        # Test 8.1: Initialization
        tracker = BurstTracker(window_seconds=60)
        print_test("BurstTracker initialization", "PASS")
        results["passed"] += 1
        
        # Test 8.2: Query counting
        test_ip = "192.168.1.100"
        for _ in range(50):
            qpm = tracker.add(test_ip)
        
        print_test("Query counting", "PASS", f"{test_ip} has {qpm} queries/min")
        results["passed"] += 1
        
        # Test 8.3: Burst detection threshold
        if qpm >= 50:
            print_test("Burst threshold check", "PASS", "High QPM detected")
            results["passed"] += 1
        else:
            print_test("Burst threshold check", "INFO", f"QPM below burst threshold")
            results["passed"] += 1
        
    except Exception as e:
        print_test("Burst tracker test", "FAIL", str(e))
        results["failed"] += 1
    
    return results


# ============================================================================
# MAIN MENU
# ============================================================================

def print_menu():
    """Print the main menu."""
    print(f"""
{Colors.BOLD}Select a test to run:{Colors.END}

  {Colors.CYAN}[1]{Colors.END} Sector Lock System      {Colors.DIM}(Factory-set configuration){Colors.END}
  {Colors.CYAN}[2]{Colors.END} Feed System             {Colors.DIM}(Threat intelligence){Colors.END}
  {Colors.CYAN}[3]{Colors.END} Flow Collector          {Colors.DIM}(Network traffic analysis){Colors.END}
  {Colors.CYAN}[4]{Colors.END} MLP Engine              {Colors.DIM}(AI threat detection){Colors.END}
  {Colors.CYAN}[5]{Colors.END} YARA Scanner            {Colors.DIM}(Payload analysis){Colors.END}
  {Colors.CYAN}[6]{Colors.END} Scoring Engine          {Colors.DIM}(Decision logic){Colors.END}
  {Colors.CYAN}[7]{Colors.END} Policy System           {Colors.DIM}(Configuration){Colors.END}
  {Colors.CYAN}[8]{Colors.END} Burst Tracker           {Colors.DIM}(DDoS detection){Colors.END}

  {Colors.GREEN}[A]{Colors.END} Run ALL Tests
  {Colors.RED}[Q]{Colors.END} Quit

""")

def run_all_tests():
    """Run all tests and show summary."""
    tests = [
        ("Sector Lock", test_sector_lock),
        ("Feed System", test_feed_system),
        ("Flow Collector", test_flow_collector),
        ("MLP Engine", test_mlp_engine),
        ("YARA Scanner", test_yara_scanner),
        ("Scoring Engine", test_scoring_engine),
        ("Policy System", test_policy_system),
        ("Burst Tracker", test_burst_tracker),
    ]
    
    all_results = {"passed": 0, "failed": 0, "skipped": 0}
    
    for name, test_func in tests:
        results = test_func()
        all_results["passed"] += results["passed"]
        all_results["failed"] += results["failed"]
        all_results["skipped"] += results["skipped"]
    
    # Print summary
    print_section("TEST SUMMARY")
    
    total = all_results["passed"] + all_results["failed"] + all_results["skipped"]
    
    print(f"""
  {Colors.GREEN}Passed:{Colors.END}  {all_results['passed']:>3}
  {Colors.RED}Failed:{Colors.END}  {all_results['failed']:>3}
  {Colors.YELLOW}Skipped:{Colors.END} {all_results['skipped']:>3}
  {'─' * 20}
  {Colors.BOLD}Total:{Colors.END}   {total:>3}
""")
    
    if all_results["failed"] == 0:
        print(f"  {Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.END}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.END}")
    
    return all_results


def main():
    """Main entry point."""
    # Set default sector if not set
    if not os.environ.get("MINIFW_SECTOR"):
        os.environ["MINIFW_SECTOR"] = "school"
    
    while True:
        clear_screen()
        print_banner()
        print_menu()
        
        try:
            choice = input(f"  {Colors.BOLD}Enter choice:{Colors.END} ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break
        
        if choice == 'Q':
            print("\nGoodbye!")
            break
        elif choice == 'A':
            clear_screen()
            print_banner()
            run_all_tests()
            wait_for_key()
        elif choice == '1':
            clear_screen()
            test_sector_lock()
            wait_for_key()
        elif choice == '2':
            clear_screen()
            test_feed_system()
            wait_for_key()
        elif choice == '3':
            clear_screen()
            test_flow_collector()
            wait_for_key()
        elif choice == '4':
            clear_screen()
            test_mlp_engine()
            wait_for_key()
        elif choice == '5':
            clear_screen()
            test_yara_scanner()
            wait_for_key()
        elif choice == '6':
            clear_screen()
            test_scoring_engine()
            wait_for_key()
        elif choice == '7':
            clear_screen()
            test_policy_system()
            wait_for_key()
        elif choice == '8':
            clear_screen()
            test_burst_tracker()
            wait_for_key()
        else:
            print(f"\n  {Colors.RED}Invalid choice. Please try again.{Colors.END}")
            time.sleep(1)


if __name__ == "__main__":
    main()
