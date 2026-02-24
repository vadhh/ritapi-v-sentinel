"""
Tests for the ops_alert sub-app (alert dashboard, chart data).

Run with:
    python manage.py test ops.ops_alert -v2
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from alert.models import Alert

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
class OpsAlertDashboardTests(TestCase):
    """Tests for /ops/alerts/ dashboard and chart-data endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )
        # Create a few alerts for filtering tests
        cls.alert_high = Alert.objects.create(
            alert_type="Brute Force",
            ip_address="10.0.0.1",
            detail="SSH brute force attempt",
            severity="high",
        )
        cls.alert_low = Alert.objects.create(
            alert_type="Port Scan",
            ip_address="192.168.1.5",
            detail="Nmap scan detected",
            severity="low",
        )
        cls.alert_critical = Alert.objects.create(
            alert_type="SQL Injection",
            ip_address="10.0.0.99",
            detail="SQLi payload",
            severity="critical",
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_alert_dashboard_renders(self):
        """GET /ops/alerts/ should return 200 with alerts in context."""
        resp = self.client.get("/ops/alerts/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("alerts", resp.context)

    def test_alert_dashboard_search(self):
        """GET ?q=10.0.0 should filter to matching alerts."""
        resp = self.client.get("/ops/alerts/?q=10.0.0")
        self.assertEqual(resp.status_code, 200)
        alert_ips = [a.ip_address for a in resp.context["alerts"]]
        self.assertIn("10.0.0.1", alert_ips)
        self.assertNotIn("192.168.1.5", alert_ips)

    def test_alert_dashboard_filter_severity(self):
        """GET ?severity=high should return only high-severity alerts."""
        resp = self.client.get("/ops/alerts/?severity=high")
        self.assertEqual(resp.status_code, 200)
        for alert in resp.context["alerts"]:
            self.assertEqual(alert.severity, "high")

    def test_alert_dashboard_no_results_message(self):
        """Filters with no matches should set error_message."""
        resp = self.client.get("/ops/alerts/?q=nonexistent_ip_xyz")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["error_message"])

    def test_alert_chart_data_all(self):
        """GET chart-data should return JSON with labels and data."""
        resp = self.client.get("/ops/alerts/alert_chart_data/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("labels", data)
        self.assertIn("data", data)
        self.assertEqual(len(data["labels"]), 4)
        self.assertEqual(len(data["data"]), 4)

    def test_alert_chart_data_7d(self):
        """GET chart-data?period=7d should return filtered JSON."""
        resp = self.client.get("/ops/alerts/alert_chart_data/?period=7d")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("labels", data)
        self.assertIn("data", data)
