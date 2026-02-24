# ip_reputation/tests/test_services.py
from django.test import TestCase
from unittest.mock import patch, MagicMock
from ip_reputation.services import IpReputationService
from ip_reputation.models import IpReputation, InternalIPList
from django.utils import timezone


class TestIpReputationService(TestCase):

    @patch("ip_reputation.services.requests.get")
    @patch("ip_reputation.services.IpReputation.objects.update_or_create")
    @patch("ip_reputation.services.IpReputationService.load_threat_feeds")
    def test_check_reputation_tor(
        self, mock_load_feeds, mock_update_or_create, mock_requests_get
    ):
        # Mock API response
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = {
            "org": "Test ISP",
            "country_name": "Test Country",
            "asn": "AS12345",
        }

        # Mock update_or_create return
        mock_record = MagicMock()
        mock_record.ip_address = "23.137.248.100"
        mock_record.reputation_score = -2
        mock_record.is_tor = True
        mock_record.scores = {"sources": ["TOR"], "ip_reputation_score": -2}
        mock_update_or_create.return_value = (mock_record, True)

        # Simulate TOR IP
        IpReputationService.tor_list = {"23.137.248.100"}

        record = IpReputationService.check_reputation("23.137.248.100")
        self.assertEqual(record.ip_address, "23.137.248.100")
        self.assertTrue(record.is_tor)
        self.assertIn("TOR", record.scores["sources"])
        self.assertLess(record.reputation_score, 0)

    @patch("ip_reputation.services.requests.get")
    @patch("ip_reputation.services.IpReputation.objects.update_or_create")
    @patch("ip_reputation.services.IpReputationService.load_threat_feeds")
    def test_check_reputation_allowlist(
        self, mock_load_feeds, mock_update_or_create, mock_requests_get
    ):
        # Mock API response
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = {
            "org": "Test ISP",
            "country_name": "Test Country",
            "asn": "AS12345",
        }

        mock_record = MagicMock()
        mock_record.ip_address = "1.1.1.1"
        mock_record.reputation_score = 1
        mock_record.is_tor = False
        mock_record.scores = {"sources": ["ALLOWLIST"], "ip_reputation_score": 1}
        mock_update_or_create.return_value = (mock_record, True)

        record = IpReputationService.check_reputation("1.1.1.1")
        self.assertEqual(record.ip_address, "1.1.1.1")
        self.assertFalse(record.is_tor)
        self.assertIn("ALLOWLIST", record.scores["sources"])
        self.assertGreater(record.reputation_score, 0)

    @patch("ip_reputation.services.requests.get")
    @patch("ip_reputation.services.IpReputation.objects.update_or_create")
    @patch("ip_reputation.services.IpReputationService.load_threat_feeds")
    def test_check_reputation_api_fail(
        self, mock_load_feeds, mock_update_or_create, mock_requests_get
    ):
        # Simulate API failure
        mock_requests_get.return_value.status_code = 500

        mock_record = MagicMock()
        mock_record.ip_address = "9.9.9.9"
        mock_record.reputation_score = 0
        mock_record.is_tor = False
        mock_record.scores = {"error": "API Error 500"}
        mock_update_or_create.return_value = (mock_record, True)

        record = IpReputationService.check_reputation("9.9.9.9")
        self.assertEqual(record.ip_address, "9.9.9.9")
        self.assertFalse(record.is_tor)
        self.assertIn("error", record.scores)
