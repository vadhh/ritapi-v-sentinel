# asn/tests/test_views_mock.py
from rest_framework.test import APITestCase, APIClient
from unittest.mock import patch, MagicMock


class TestAsnViewsMock(APITestCase):

    def setUp(self):
        self.client = APIClient()

    @patch("asn.services.AsnScoreService.lookup_asn")
    def test_lookup_view_post_mocked(self, mock_lookup):
        # Mock return object untuk lookup_asn
        mock_lookup.return_value = MagicMock(
            id=1,
            ip_address="8.8.8.8",
            asn_number="15169",
            asn_description="GOOGLE",
            trust_score=0,
            timestamp="2025-12-11T08:00:00Z",
        )

        response = self.client.post("/asn/lookup/", {"ip": "8.8.8.8"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["asn_number"], "15169")
        self.assertEqual(response.data["ip_address"], "8.8.8.8")
        self.assertEqual(response.data["asn_description"], "GOOGLE")

    @patch("asn.views.AsnInfo.objects")
    def test_history_view_get_mocked(self, mock_objects):
        # Mock return value untuk objects.all().order_by()[:10]
        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.ip_address = "8.8.8.8"
        mock_record.asn_number = "15169"
        mock_record.asn_description = "GOOGLE"
        mock_record.trust_score = 0
        mock_record.timestamp = "2025-12-11T08:00:00Z"

        mock_queryset = MagicMock()
        mock_queryset.__getitem__.return_value = [mock_record]
        mock_objects.all.return_value.order_by.return_value = mock_queryset

        response = self.client.get("/asn/history/")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response.data[0]["asn_number"], "15169")
        self.assertEqual(response.data[0]["ip_address"], "8.8.8.8")
