from django.test import TestCase
from .models import JsonSchema
from .services import JsonEnforcerService


class JsonEnforcerServiceCRUDTests(TestCase):
    def setUp(self):
        self.schema_data = {
            "name": "Test Schema",
            "endpoint": "/api/test",
            "method": "POST",
            "schema_json": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            "description": "A test schema",
            "version": "v1",
            "rollout_mode": "enforce",
        }

    def test_create_schema(self):
        schema = JsonEnforcerService.create_schema(self.schema_data)
        self.assertEqual(schema.name, "Test Schema")
        self.assertEqual(schema.endpoint, "/api/test")
        self.assertEqual(schema.method, "POST")
        self.assertEqual(schema.rollout_mode, "enforce")
        self.assertTrue(schema.is_active)

    def test_create_duplicate_raises(self):
        JsonEnforcerService.create_schema(self.schema_data)
        with self.assertRaises(ValueError):
            JsonEnforcerService.create_schema(self.schema_data)

    def test_get_schema(self):
        created = JsonEnforcerService.create_schema(self.schema_data)
        fetched = JsonEnforcerService.get_schema(created.pk)
        self.assertEqual(fetched.pk, created.pk)
        self.assertEqual(fetched.name, "Test Schema")

    def test_get_schema_not_found(self):
        self.assertIsNone(JsonEnforcerService.get_schema(9999))

    def test_update_schema(self):
        created = JsonEnforcerService.create_schema(self.schema_data)
        updated = JsonEnforcerService.update_schema(
            created.pk, {"name": "Updated Schema", "rollout_mode": "monitor"}
        )
        self.assertEqual(updated.name, "Updated Schema")
        self.assertEqual(updated.rollout_mode, "monitor")

    def test_update_schema_not_found(self):
        self.assertIsNone(JsonEnforcerService.update_schema(9999, {"name": "X"}))

    def test_delete_schema(self):
        created = JsonEnforcerService.create_schema(self.schema_data)
        self.assertTrue(JsonEnforcerService.delete_schema(created.pk))
        self.assertIsNone(JsonEnforcerService.get_schema(created.pk))

    def test_delete_schema_not_found(self):
        self.assertFalse(JsonEnforcerService.delete_schema(9999))

    def test_list_schemas(self):
        JsonEnforcerService.create_schema(self.schema_data)
        second = dict(self.schema_data, endpoint="/api/other", name="Second")
        JsonEnforcerService.create_schema(second)
        schemas = list(JsonEnforcerService.list_schemas())
        self.assertEqual(len(schemas), 2)
        # Ordered by -timestamp, so most recent first
        self.assertEqual(schemas[0].endpoint, "/api/other")


class JsonEnforcerServiceValidationTests(TestCase):
    def setUp(self):
        self.schema = JsonSchema.objects.create(
            name="Validation Schema",
            endpoint="/api/data",
            method="POST",
            version="v1",
            rollout_mode="enforce",
            is_active=True,
            schema_json={
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name"],
            },
        )

    def test_validate_payload_valid(self):
        result = JsonEnforcerService.validate_payload(
            "/api/data", "POST", {"name": "Alice", "age": 30}
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["rollout_mode"], "enforce")

    def test_validate_payload_invalid(self):
        result = JsonEnforcerService.validate_payload(
            "/api/data", "POST", {"age": "not-a-number"}
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["rollout_mode"], "enforce")

    def test_validate_no_schema(self):
        result = JsonEnforcerService.validate_payload(
            "/api/nonexistent", "GET", {"key": "value"}
        )
        self.assertTrue(result["valid"])
        self.assertIn("No active schema", result["message"])

    def test_validate_fallback_v1(self):
        result = JsonEnforcerService.validate_payload(
            "/api/data", "POST", {"name": "Bob"}, version="v2"
        )
        self.assertTrue(result["valid"])
        self.assertIn("fallback", result["message"])
