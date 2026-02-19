"""
Tests for the ops_asn sub-app (ASN checker, config, trust score update).

Run with:
    python manage.py test ops.ops_asn -v2
"""

from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from asn.models import AsnInfo, AsnTrustConfig

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
class AsnCheckerViewTests(TestCase):
    """Tests for GET/POST /ops/asn/asn-checker/"""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )
        # Pre-existing ASN lookup record
        cls.trust_config = AsnTrustConfig.objects.create(
            asn_number="AS15169", name="Google LLC", score=80
        )
        cls.asn_record = AsnInfo.objects.create(
            ip_address="8.8.8.8",
            asn_number="AS15169",
            asn_description="Google LLC",
            trust_score=80,
            is_latest=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    # ── GET ──────────────────────────────────────────────────────────────────

    def test_get_renders(self):
        """GET /ops/asn/asn-checker/ returns 200 and history."""
        resp = self.client.get("/ops/asn/asn-checker/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "ops_template/asn_checker.html")
        self.assertIn("history", resp.context)
        self.assertIsNone(resp.context["result"])

    def test_get_search_filters_history(self):
        """GET ?search=8.8.8 should return matching rows only."""
        # Add a non-matching record
        AsnInfo.objects.create(
            ip_address="1.1.1.1", asn_number="AS13335",
            asn_description="Cloudflare", trust_score=0, is_latest=True,
        )
        resp = self.client.get("/ops/asn/asn-checker/?search=8.8.8")
        self.assertEqual(resp.status_code, 200)
        ips = [r.ip_address for r in resp.context["history"]]
        self.assertIn("8.8.8.8", ips)
        self.assertNotIn("1.1.1.1", ips)

    def test_get_unauthenticated_redirects(self):
        """Unauthenticated GET should redirect to login."""
        self.client.logout()
        resp = self.client.get("/ops/asn/asn-checker/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    # ── POST: valid IP ────────────────────────────────────────────────────────

    @patch("asn.services.AsnScoreService.lookup_asn")
    def test_post_valid_ip_returns_result(self, mock_lookup):
        """POST with a valid IP calls lookup_asn and returns result in context."""
        fake_record = AsnInfo.objects.create(
            ip_address="8.8.4.4",
            asn_number="AS15169",
            asn_description="Google LLC",
            trust_score=80,
            is_latest=True,
        )
        mock_lookup.return_value = fake_record

        resp = self.client.post(
            "/ops/asn/asn-checker/",
            {"ip": "8.8.4.4"},
        )
        self.assertEqual(resp.status_code, 200)
        mock_lookup.assert_called_once_with("8.8.4.4")
        self.assertIsNotNone(resp.context["result"])
        self.assertEqual(resp.context["result"].ip_address, "8.8.4.4")

    @patch("asn.services.AsnScoreService.lookup_asn")
    def test_post_valid_ip_updates_trust_score(self, mock_lookup):
        """After lookup, trust_score is refreshed from AsnTrustConfig and saved."""
        record = AsnInfo.objects.create(
            ip_address="8.8.4.4",
            asn_number="AS15169",
            asn_description="Google LLC",
            trust_score=0,  # stale score
            is_latest=True,
        )
        mock_lookup.return_value = record

        self.client.post("/ops/asn/asn-checker/", {"ip": "8.8.4.4"})

        record.refresh_from_db()
        # trust_score should now match AsnTrustConfig AS15169 = 80
        self.assertEqual(record.trust_score, 80)

    @patch("asn.services.AsnScoreService.lookup_asn")
    def test_post_no_record_shows_error(self, mock_lookup):
        """POST with IP that has no ASN record shows error_message in context."""
        mock_lookup.return_value = None

        resp = self.client.post("/ops/asn/asn-checker/", {"ip": "10.0.0.1"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["error_message"])
        self.assertIn("10.0.0.1", resp.context["error_message"])
        self.assertIsNone(resp.context["result"])

    # ── POST: invalid IP ─────────────────────────────────────────────────────

    def test_post_invalid_ip_shows_error(self):
        """POST with non-IP string shows validation error, no lookup called."""
        resp = self.client.post("/ops/asn/asn-checker/", {"ip": "not-an-ip"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["error_message"])
        self.assertIn("not-an-ip", resp.context["error_message"])
        self.assertIsNone(resp.context["result"])

    def test_post_empty_ip_field_skips_lookup(self):
        """POST with empty ip field should render without error or result."""
        resp = self.client.post("/ops/asn/asn-checker/", {"ip": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["result"])
        self.assertIsNone(resp.context["error_message"])

    def test_post_unauthenticated_redirects(self):
        """Unauthenticated POST should redirect to login."""
        self.client.logout()
        resp = self.client.post("/ops/asn/asn-checker/", {"ip": "8.8.8.8"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])


@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class AsnConfigViewTests(TestCase):
    """Tests for GET /ops/asn/asn-config/"""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )
        cls.cfg_google = AsnTrustConfig.objects.create(
            asn_number="AS15169", name="Google LLC", score=80
        )
        cls.cfg_cloudflare = AsnTrustConfig.objects.create(
            asn_number="AS13335", name="Cloudflare", score=50
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_get_renders(self):
        """GET /ops/asn/asn-config/ returns 200 with configs in context."""
        resp = self.client.get("/ops/asn/asn-config/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "ops_template/asn_config.html")
        self.assertIn("configs", resp.context)
        asn_numbers = [c.asn_number for c in resp.context["configs"]]
        self.assertIn("AS15169", asn_numbers)
        self.assertIn("AS13335", asn_numbers)

    def test_get_search_filters_configs(self):
        """GET ?cfg_search=AS15169 should return only matching config."""
        resp = self.client.get("/ops/asn/asn-config/?cfg_search=AS15169")
        self.assertEqual(resp.status_code, 200)
        asn_numbers = [c.asn_number for c in resp.context["configs"]]
        self.assertIn("AS15169", asn_numbers)
        self.assertNotIn("AS13335", asn_numbers)

    def test_get_unauthenticated_redirects(self):
        """Unauthenticated GET should redirect to login."""
        self.client.logout()
        resp = self.client.get("/ops/asn/asn-config/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])


@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class AsnUpdateScoreViewTests(TestCase):
    """Tests for POST /ops/asn/asn-update-score/ (create and update trust configs)."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )
        cls.existing_cfg = AsnTrustConfig.objects.create(
            asn_number="AS15169", name="Google LLC", score=80
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    # ── Create ────────────────────────────────────────────────────────────────

    def test_post_creates_new_trust_config(self):
        """POST with a new ASN number creates an AsnTrustConfig and redirects."""
        self.assertFalse(AsnTrustConfig.objects.filter(asn_number="AS13335").exists())

        resp = self.client.post(
            "/ops/asn/asn-update-score/",
            {"asn_number": "AS13335", "name": "Cloudflare", "score": 60},
        )
        self.assertRedirects(resp, "/ops/asn/asn-config/", fetch_redirect_response=False)
        cfg = AsnTrustConfig.objects.get(asn_number="AS13335")
        self.assertEqual(cfg.name, "Cloudflare")
        self.assertEqual(float(cfg.score), 60.0)

    # ── Update ────────────────────────────────────────────────────────────────

    def test_post_updates_existing_trust_config(self):
        """POST with existing ASN number updates score and name."""
        resp = self.client.post(
            "/ops/asn/asn-update-score/",
            {"asn_number": "AS15169", "name": "Google LLC Updated", "score": -50},
        )
        self.assertRedirects(resp, "/ops/asn/asn-config/", fetch_redirect_response=False)
        self.existing_cfg.refresh_from_db()
        self.assertEqual(self.existing_cfg.name, "Google LLC Updated")
        self.assertEqual(float(self.existing_cfg.score), -50.0)

    # ── GET (no-op) ───────────────────────────────────────────────────────────

    def test_get_redirects_without_changes(self):
        """GET to asn_update_score should redirect without touching the DB."""
        count_before = AsnTrustConfig.objects.count()
        resp = self.client.get("/ops/asn/asn-update-score/")
        self.assertRedirects(resp, "/ops/asn/asn-config/", fetch_redirect_response=False)
        self.assertEqual(AsnTrustConfig.objects.count(), count_before)

    # ── Auth ─────────────────────────────────────────────────────────────────

    def test_post_unauthenticated_redirects(self):
        """Unauthenticated POST should redirect to login."""
        self.client.logout()
        resp = self.client.post(
            "/ops/asn/asn-update-score/",
            {"asn_number": "AS9999", "name": "Evil Corp", "score": -100},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])
        self.assertFalse(AsnTrustConfig.objects.filter(asn_number="AS9999").exists())
