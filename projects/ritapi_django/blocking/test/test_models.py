from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from blocking.models import BlockedIP

class TestBlockedIPModel(TestCase):

    def test_blocked_ip_creation(self):
        """Test pembuatan dasar objek BlockedIP."""
        ip = "192.168.1.1"
        reason = "Test Block"
        blocked_ip = BlockedIP.objects.create(
            ip_address=ip,
            reason=reason,
            severity="high",
            country="US",
            active=True
        )
        self.assertEqual(blocked_ip.ip_address, ip)
        self.assertEqual(blocked_ip.reason, reason)
        self.assertEqual(blocked_ip.severity, "high")
        self.assertTrue(blocked_ip.active)

    def test_is_active_permanent_block(self):
        """Test is_active() untuk blokir permanen (expires_at=None)."""
        blocked_ip = BlockedIP.objects.create(
            ip_address="1.1.1.1",
            reason="Permanent Block",
            active=True,
            expires_at=None
        )
        self.assertTrue(blocked_ip.is_active())

    def test_is_active_temporary_block_active(self):
        """Test is_active() untuk blokir temporer yang masih aktif."""
        future_time = timezone.now() + timedelta(minutes=5)
        blocked_ip = BlockedIP.objects.create(
            ip_address="2.2.2.2",
            reason="Temporary Block",
            active=True,
            expires_at=future_time
        )
        self.assertTrue(blocked_ip.is_active())

    def test_is_active_temporary_block_expired(self):
        """Test is_active() untuk blokir temporer yang sudah kedaluwarsa."""
        past_time = timezone.now() - timedelta(minutes=5)
        blocked_ip = BlockedIP.objects.create(
            ip_address="3.3.3.3",
            reason="Expired Block",
            active=True,
            expires_at=past_time
        )
        # is_active() akan mengembalikan False karena sudah expired
        self.assertFalse(blocked_ip.is_active())

    def test_str_representation(self):
        """Test representasi string objek BlockedIP."""
        blocked_ip = BlockedIP.objects.create(
            ip_address="4.4.4.4",
            reason="Test",
            severity="critical"
        )
        self.assertEqual(str(blocked_ip), "[CRITICAL] 4.4.4.4")