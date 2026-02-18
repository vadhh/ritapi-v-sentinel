"""
Tests for the ops root dashboard view.

Run with:
    python manage.py test ops.tests -v2
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from alert.models import Alert
from blocking.models import BlockedIP
from log_channel.models import RequestLog

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
class OpsRootDashboardTests(TestCase):
    """Tests for /ops/ root dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )
        cls.regular_user = User.objects.create_user(
            username="viewer", email="viewer@test.local", password="TestPass123!"
        )

    def setUp(self):
        self.client = Client()

    def test_dashboard_requires_superuser(self):
        """Regular user GET /ops/ should redirect to login."""
        self.client.login(username="viewer", password="TestPass123!")
        resp = self.client.get("/ops/", follow=False)
        self.assertIn(resp.status_code, [301, 302])

    def test_dashboard_renders_for_superuser(self):
        """Superuser GET /ops/ should return 200."""
        self.client.login(username="admin", password="TestPass123!")
        resp = self.client.get("/ops/")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_context_has_stats(self):
        """Context should include aggregated statistics."""
        # Seed some data
        Alert.objects.create(
            alert_type="test", ip_address="10.0.0.1",
            detail="d", severity="high",
        )
        BlockedIP.objects.create(
            ip_address="10.0.0.2", reason="test", severity="high", active=True
        )
        RequestLog.objects.create(
            method="GET", path="/test", ip_address="10.0.0.3",
            action="ALLOW", body_size=0, score=0.1, label="clean",
        )
        RequestLog.objects.create(
            method="POST", path="/bad", ip_address="10.0.0.4",
            action="BLOCK", body_size=128, score=0.9, label="gambling_possible",
        )

        self.client.login(username="admin", password="TestPass123!")
        resp = self.client.get("/ops/")
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx["total_alerts"], 1)
        self.assertEqual(ctx["total_blocked"], 1)
        self.assertEqual(ctx["total_requests_allow"], 1)
        self.assertEqual(ctx["total_requests_block"], 1)
