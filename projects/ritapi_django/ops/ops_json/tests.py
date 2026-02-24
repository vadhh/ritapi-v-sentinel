"""
Tests for the ops_json sub-app (JsonSchema CRUD via ops dashboard).

Run with:
    python manage.py test ops.ops_json -v2
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings

from json_schema.models import JsonSchema

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
class OpsJsonSchemaDashboardTests(TestCase):
    """Tests for /ops/json-schema/ dashboard and CRUD."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="TestPass123!"
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="TestPass123!")

    def test_dashboard_renders(self):
        """GET /ops/json-schema/ should return 200 with page_obj."""
        resp = self.client.get("/ops/json-schema/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("page_obj", resp.context)

    def test_create_schema(self):
        """POST with valid data should create a schema."""
        resp = self.client.post(
            "/ops/json-schema/create/",
            {
                "name": "Test Schema",
                "endpoint": "/api/test",
                "method": "POST",
                "schema_json": '{"type": "object"}',
                "description": "A test schema",
                "rollout_mode": "monitor",
                "version": "v1",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertTrue(JsonSchema.objects.filter(name="Test Schema").exists())

    def test_create_invalid_json(self):
        """POST with invalid schema_json should return 400."""
        resp = self.client.post(
            "/ops/json-schema/create/",
            {
                "name": "Bad Schema",
                "endpoint": "/api/bad",
                "method": "POST",
                "schema_json": "not-valid-json{{{",
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_update_schema(self):
        """POST update should modify existing schema."""
        schema = JsonSchema.objects.create(
            name="Original",
            endpoint="/api/orig",
            method="GET",
            schema_json={"type": "object"},
            version="v1",
        )
        resp = self.client.post(
            f"/ops/json-schema/update/{schema.pk}/",
            {
                "name": "Updated",
                "endpoint": "/api/orig",
                "method": "GET",
                "schema_json": '{"type": "array"}',
                "version": "v1",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        schema.refresh_from_db()
        self.assertEqual(schema.name, "Updated")

    def test_update_not_found(self):
        """POST update nonexistent pk should return 404."""
        resp = self.client.post(
            "/ops/json-schema/update/99999/",
            {
                "name": "x",
                "endpoint": "/x",
                "schema_json": "{}",
            },
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_schema(self):
        """POST delete should remove schema from DB."""
        schema = JsonSchema.objects.create(
            name="ToDelete",
            endpoint="/api/del",
            method="DELETE",
            schema_json={"type": "object"},
            version="v1",
        )
        resp = self.client.post(f"/ops/json-schema/delete/{schema.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertFalse(JsonSchema.objects.filter(pk=schema.pk).exists())

    def test_toggle_schema(self):
        """POST toggle should flip is_active."""
        schema = JsonSchema.objects.create(
            name="Toggle",
            endpoint="/api/toggle",
            method="POST",
            schema_json={"type": "object"},
            version="v1",
            is_active=True,
        )
        resp = self.client.post(f"/ops/json-schema/toggle/{schema.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["is_active"])
        schema.refresh_from_db()
        self.assertFalse(schema.is_active)
