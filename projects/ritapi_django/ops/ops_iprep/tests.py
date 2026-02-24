"""
Tests for the ops_iprep sub-app (IP reputation dashboard, InternalIPList CRUD).

Run with:
    python manage.py test ops.ops_iprep -v2
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from ip_reputation.models import InternalIPList

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
class OpsIpReputationDashboardTests(TestCase):
    """Tests for /ops/ip-reputation/ dashboard (GET + POST)."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_dashboard_renders(self):
        """GET /ops/ip-reputation/ should return 200."""
        resp = self.client.get("/ops/ip-reputation/")
        self.assertEqual(resp.status_code, 200)

    @patch("ip_reputation.services.IpReputationService.check_reputation")
    def test_dashboard_post_valid_ip(self, mock_check):
        """POST with valid IP should return result in context."""
        mock_check.return_value = {
            "ip": "8.8.8.8",
            "score": 95,
            "isp": "Google",
            "country": "US",
        }
        resp = self.client.post("/ops/ip-reputation/", {"ip_address": "8.8.8.8"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["result"])
        mock_check.assert_called_once_with("8.8.8.8")

    def test_dashboard_post_invalid_ip(self):
        """POST with invalid IP should return error_message."""
        resp = self.client.post("/ops/ip-reputation/", {"ip_address": "not-an-ip"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["error_message"])


@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class OpsInternalIPListTests(TestCase):
    """Tests for /ops/ip-reputation/internal-ip/ CRUD."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_internal_ip_dashboard_renders(self):
        """GET /ops/ip-reputation/internal-ip/ should return 200."""
        resp = self.client.get("/ops/ip-reputation/internal-ip/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("page_obj", resp.context)

    def test_internal_ip_create(self):
        """POST create with valid data should create entry."""
        resp = self.client.post(
            "/ops/ip-reputation/internal-ip/create/",
            {
                "ip_address": "10.0.0.1",
                "list_type": "allow",
                "reason": "Trusted server",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertTrue(InternalIPList.objects.filter(ip_address="10.0.0.1").exists())

    def test_internal_ip_create_invalid_ip(self):
        """POST with invalid IP should return 400."""
        resp = self.client.post(
            "/ops/ip-reputation/internal-ip/create/",
            {
                "ip_address": "not-an-ip",
                "list_type": "allow",
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_internal_ip_update(self):
        """POST update should modify existing entry."""
        entry = InternalIPList.objects.create(
            ip_address="10.0.0.2", list_type="allow", reason="Old reason"
        )
        resp = self.client.post(
            f"/ops/ip-reputation/internal-ip/update/{entry.pk}/",
            {
                "ip_address": "10.0.0.2",
                "list_type": "deny",
                "reason": "Changed to deny",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        entry.refresh_from_db()
        self.assertEqual(entry.list_type, "deny")
        self.assertEqual(entry.reason, "Changed to deny")

    def test_internal_ip_delete(self):
        """POST delete should remove entry."""
        entry = InternalIPList.objects.create(
            ip_address="10.0.0.3", list_type="deny", reason="To delete"
        )
        resp = self.client.post(f"/ops/ip-reputation/internal-ip/delete/{entry.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertFalse(InternalIPList.objects.filter(pk=entry.pk).exists())
