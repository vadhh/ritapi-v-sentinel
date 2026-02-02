from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch, MagicMock

class TestAlertViews(APITestCase):

    def setUp(self):
        self.client = APIClient()

    @patch("alert.services.AlertService.create_alert")
    def test_create_alert_post_mocked(self, mock_create_alert):
        mock_create_alert.return_value = MagicMock(id=1)
        response = self.client.post(
            "/alerts/create/",
            {"alert_type": "Test", "ip_address": "1.2.3.4", "detail": "Detected XSS"},
            format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["id"], 1)

    @patch("alert.services.Alert.objects")
    def test_list_alerts_get_mocked(self, mock_alerts):
        mock_alert = MagicMock(
            id=1, alert_type="XSS", ip_address="1.2.3.4", severity="critical",
            detail="Detected XSS", resolved=False, timestamp="2025-12-11T08:00:00Z"
        )
        mock_alerts.all.return_value.order_by.return_value.__getitem__.return_value = [mock_alert]
        response = self.client.get("/alerts/list/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], 1)
