"""
Tests for the ops_geoblock sub-app (GeoBlockSetting CRUD).

Run with:
    python manage.py test ops.ops_geoblock -v2
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from ops.ops_geoblock.models import GeoBlockSetting

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
class GeoBlockDashboardTests(TestCase):
    """Tests for geo-block dashboard and CRUD operations."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_dashboard_renders(self):
        """GET /ops/geo-block/ should return 200."""
        resp = self.client.get("/ops/geo-block/")
        self.assertEqual(resp.status_code, 200)

    def test_create_entry(self):
        """POST create with valid data should create entry in DB."""
        resp = self.client.post("/ops/geo-block/create/", {
            "country_code": "CN",
            "action": "block",
            "description": "Test block",
            "is_active": "true",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertTrue(GeoBlockSetting.objects.filter(country_code="CN").exists())

    def test_create_missing_country_code(self):
        """POST create without country_code should return 400."""
        resp = self.client.post("/ops/geo-block/create/", {
            "action": "block",
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_create_upserts_existing(self):
        """POST same country_code should update existing entry."""
        GeoBlockSetting.objects.create(
            country_code="US", action="block", description="Old"
        )
        resp = self.client.post("/ops/geo-block/create/", {
            "country_code": "US",
            "action": "allow",
            "description": "Updated",
            "is_active": "true",
        })
        self.assertEqual(resp.status_code, 200)
        entry = GeoBlockSetting.objects.get(country_code="US")
        self.assertEqual(entry.action, "allow")
        self.assertEqual(entry.description, "Updated")

    def test_update_entry(self):
        """POST update should modify existing entry."""
        entry = GeoBlockSetting.objects.create(
            country_code="RU", action="block", description="Old"
        )
        resp = self.client.post(f"/ops/geo-block/update/{entry.pk}/", {
            "country_code": "RU",
            "action": "allow",
            "description": "New desc",
            "is_active": "true",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        entry.refresh_from_db()
        self.assertEqual(entry.action, "allow")
        self.assertEqual(entry.description, "New desc")

    def test_update_not_found(self):
        """POST update nonexistent pk should return 404."""
        resp = self.client.post("/ops/geo-block/update/99999/", {
            "country_code": "XX",
            "action": "block",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete_entry(self):
        """POST delete should remove entry from DB."""
        entry = GeoBlockSetting.objects.create(
            country_code="IR", action="block"
        )
        resp = self.client.post(f"/ops/geo-block/delete/{entry.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertFalse(GeoBlockSetting.objects.filter(pk=entry.pk).exists())

    def test_delete_not_found(self):
        """POST delete nonexistent pk should return 404."""
        resp = self.client.post("/ops/geo-block/delete/99999/")
        self.assertEqual(resp.status_code, 404)
