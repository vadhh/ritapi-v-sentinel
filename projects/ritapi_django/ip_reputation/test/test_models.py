from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from ip_reputation.models import IpReputation, InternalIPList


class TestModels(TestCase):

    def test_ipreputation_str(self):
        record = IpReputation(ip_address="8.8.8.8", reputation_score=0.5)
        self.assertEqual(str(record), "8.8.8.8 - 0.5")

    def test_internal_iplist_is_expired(self):
        expired_entry = InternalIPList(
            ip_address="10.0.0.1",
            list_type="allow",
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(expired_entry.is_expired())

        future_entry = InternalIPList(
            ip_address="10.0.0.2",
            list_type="deny",
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(future_entry.is_expired())
