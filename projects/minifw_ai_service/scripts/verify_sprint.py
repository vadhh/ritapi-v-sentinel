#!/usr/bin/env python3
import os
import sys
import unittest
import shutil
import json
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

class TestHardening(unittest.TestCase):
    def setUp(self):
        # Clear env vars to test fail-fast
        if "MINIFW_SECRET_KEY" in os.environ:
            del os.environ["MINIFW_SECRET_KEY"]
        if "MINIFW_ADMIN_PASSWORD" in os.environ:
            del os.environ["MINIFW_ADMIN_PASSWORD"]

    def test_jwt_fail_fast(self):
        print("\n[TEST] JWT Fail-Fast")
        # Should raise ValueError if env var missing
        try:
            from app.services.auth import token_service
            import importlib
            importlib.reload(token_service)
            self.fail("Did not raise ValueError when MINIFW_SECRET_KEY is missing")
        except ValueError as e:
            print(f"✅ Correctly raised: {e}")
        except ImportError:
            # Should not happen
            self.fail("Import error instead of ValueError")

    def test_symlink_bypass(self):
        print("\n[TEST] Symlink Bypass Detection")
        # Setup env
        os.environ["MINIFW_SECRET_KEY"] = "test-key"
        from app.services.policy import update_policy_service
        
        # Setup: Link /tmp/minifw_fake_log -> /etc/passwd
        # We use /etc/passwd because it definitely exists and is readable, so realpath works predictably
        target = "/etc/passwd"
        link = "/tmp/minifw_fake_log"
        if os.path.exists(link):
            os.remove(link)
        try:
            os.symlink(target, link)
        except OSError:
            print("⚠️  Skipping symlink test (insufficient privileges to create symlink)")
            return

        try:
            update_policy_service.update_collectors(
                dnsmasq_log_path=link,
                zeek_ssl_log_path="/tmp/ssl.log",
                use_zeek_sni=False
            )
            self.fail("FAILED: System allowed access to /etc/passwd via symlink!")
        except ValueError as e:
            if "Security Error" in str(e):
                print(f"✅ Correctly blocked symlink-based traversal: {e}")
            else:
                self.fail(f"Blocked but with wrong error: {e}")
        finally:
            if os.path.exists(link):
                os.remove(link)

    def test_partial_path_traversal(self):
        print("\n[TEST] Partial Path Traversal (/tmp_fake)")
        from app.services.policy import update_policy_service
        
        # Test path that starts with allowed prefix string but is a sibling directory
        # e.g. allowed: /tmp
        # attempt: /tmp_fake/log
        
        bad_path = "/tmp_fake_dir/data.log"
        
        try:
            update_policy_service.update_collectors(
                dnsmasq_log_path=bad_path,
                zeek_ssl_log_path="/tmp/ssl.log",
                use_zeek_sni=False
            )
            self.fail(f"FAILED: Partial path traversal allowed for {bad_path}")
        except ValueError as e:
            if "Security Error" in str(e):
                print(f"✅ Correctly blocked partial path: {e}")
            else:
                self.fail(f"Blocked but with wrong error: {e}")

    def test_env_file_permissions(self):
        print("\n[TEST] Systemd Environment Permissions")
        env_file = "/etc/minifw/minifw.env"
        
        if not os.path.exists(env_file):
            print("⚠️  Skipping env permission test (file not found - maybe not running as root/installed)")
            return

        stat = os.stat(env_file)
        mode = stat.st_mode & 0o777
        
        # Check 600 (owner read/write only)
        if mode != 0o600:
            # If we are strictly checking 600. 
            # Note: If verify_sprint.py created it, it might be different, but install_systemd.sh sets 600.
            self.fail(f"FAILED: /etc/minifw/minifw.env has insecure permissions: {oct(mode)}. Expected 0o600.")
        
        print(f"✅ Secure permissions confirmed: {oct(mode)}")

    def test_atomic_concurrency(self):
        print("\n[TEST] Atomic Concurrency")
        from app.services.policy import update_policy_service
        
        # Create dummy policy
        policy_path = "/tmp/test_policy.json"
        with open(policy_path, 'w') as f:
            json.dump({"test": 0}, f)
        
        os.environ["MINIFW_POLICY"] = policy_path
        
        failures = []
        
        def update_worker(i):
            try:
                update_policy_service._save_policy({"test": i})
            except Exception as e:
                failures.append(f"Thread {i}: {e}")
                
        threads = []
        for i in range(100): # High load stress test
            t = threading.Thread(target=update_worker, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        if failures:
            self.fail(f"Concurrency caused failures: {failures}")
            
        # Check integrity
        try:
            with open(policy_path, 'r') as f:
                data = json.load(f)
            # Check not empty (json.load would raise error if empty)
            print(f"✅ Policy file is valid JSON after concurrent writes. Last value: {data}")
        except Exception as e:
            self.fail(f"Corrupted or empty JSON file: {e}")

if __name__ == '__main__':
    unittest.main()
