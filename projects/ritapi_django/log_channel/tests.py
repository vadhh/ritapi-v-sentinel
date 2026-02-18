from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import RequestLog


class RequestLogModelTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", password="admin-pass-123"
        )
        self.client.login(username="admin", password="admin-pass-123")
        self.log_allow = RequestLog.objects.create(
            ip_address="10.0.0.1",
            path="/api/data",
            method="GET",
            body_size=0,
            score=0.1,
            label="clean_or_unknown",
            action="allow",
        )
        self.log_block = RequestLog.objects.create(
            ip_address="10.0.0.2",
            path="/api/data",
            method="POST",
            body_size=256,
            score=0.95,
            label="gambling_possible",
            action="block",
            reasons="High risk score",
        )
        self.log_monitor = RequestLog.objects.create(
            ip_address="10.0.0.3",
            path="/api/check",
            method="GET",
            body_size=0,
            score=0.5,
            label="suspicious",
            action="monitor",
        )

    def test_create_requestlog(self):
        self.assertEqual(RequestLog.objects.count(), 3)
        self.assertEqual(self.log_block.ip_address, "10.0.0.2")
        self.assertEqual(self.log_block.reasons, "High risk score")

    def test_status_property_allow(self):
        self.assertEqual(self.log_allow.status, "SUCCESS")

    def test_status_property_block(self):
        self.assertEqual(self.log_block.status, "FAIL")

    def test_status_property_monitor(self):
        self.assertEqual(self.log_monitor.status, "MONITOR")

    def test_requestlog_data_api(self):
        response = self.client.get(reverse("requestlog_data"))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 3)

    def test_requestlog_data_filter_action(self):
        response = self.client.get(reverse("requestlog_data"), {"action": "block"})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["action"], "block")
