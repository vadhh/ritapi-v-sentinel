"""
Tests for the ops_blocking sub-app (blocked IP dashboard, block/unblock, map).

Run with:
    python manage.py test ops.ops_blocking -v2
"""

from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from blocking.models import BlockedIP

MIDDLEWARE_FOR_TESTS = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "authentication.middleware.OpsAuthMiddleware",
]

TEST_DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class OpsBlockingDashboardTests(TestCase):
    """Tests for /ops/blocked-ips/ dashboard and related endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )
        cls.blocked_active = BlockedIP.objects.create(
            ip_address="10.0.0.1", reason="Brute force", severity="high",
            active=True, latitude=39.9, longitude=116.4,
            country="CN", country_name="China",
        )
        cls.blocked_inactive = BlockedIP.objects.create(
            ip_address="192.168.1.1", reason="Old scan", severity="low",
            active=False,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_dashboard_renders(self):
        """GET /ops/blocked-ips/ should return 200."""
        resp = self.client.get("/ops/blocked-ips/")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_search(self):
        """GET ?q=10.0 should filter to matching IPs."""
        resp = self.client.get("/ops/blocked-ips/?q=10.0")
        self.assertEqual(resp.status_code, 200)
        ips = [b.ip_address for b in resp.context["blocked_ips"]]
        self.assertIn("10.0.0.1", ips)
        self.assertNotIn("192.168.1.1", ips)

    def test_dashboard_filter_status(self):
        """GET ?status=active should return only active blocked IPs."""
        resp = self.client.get("/ops/blocked-ips/?status=active")
        self.assertEqual(resp.status_code, 200)
        for entry in resp.context["blocked_ips"]:
            self.assertTrue(entry.active)

    @patch("blocking.services.BlockingService.unblock_ip")
    def test_unblock_ip(self, mock_unblock):
        """GET unblock should call service and redirect."""
        mock_unblock.return_value = self.blocked_active
        resp = self.client.get("/ops/blocked-ips/unblock/10.0.0.1/", follow=False)
        self.assertIn(resp.status_code, [301, 302])
        mock_unblock.assert_called_once_with("10.0.0.1")

    @patch("blocking.services.BlockingService.block_ip")
    def test_block_ip_manual(self, mock_block):
        """GET block should call service and redirect."""
        mock_block.return_value = MagicMock()
        resp = self.client.get("/ops/blocked-ips/block/172.16.0.1/", follow=False)
        self.assertIn(resp.status_code, [301, 302])
        mock_block.assert_called_once_with(
            "172.16.0.1",
            reason="Manual block from dashboard",
            severity="high",
            duration_minutes=None,
        )

    def test_blocked_ip_map_renders(self):
        """GET /ops/blocked-ips/blocked-map/ should return 200."""
        resp = self.client.get("/ops/blocked-ips/blocked-map/")
        self.assertEqual(resp.status_code, 200)

    def test_blocked_ip_data_json(self):
        """GET data endpoint should return JSON with active blocked IPs."""
        resp = self.client.get("/ops/blocked-ips/blocked-map/data/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("data", data)
        # Only active IPs with lat/lon should appear
        ips = [entry["ip"] for entry in data["data"]]
        self.assertIn("10.0.0.1", ips)
        # Inactive IP should not appear
        self.assertNotIn("192.168.1.1", ips)
