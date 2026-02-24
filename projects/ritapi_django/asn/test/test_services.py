# asn/tests/test_services.py
from django.test import TestCase
from unittest.mock import patch, MagicMock
from asn.services import AsnScoreService
from asn.models import AsnTrustConfig, AsnInfo


class TestAsnScoreService(TestCase):

    def test_get_trust_score_existing(self):
        config = AsnTrustConfig.objects.create(
            asn_number="12345", name="Test ASN", score=75
        )
        score = AsnScoreService.get_trust_score("12345")
        self.assertEqual(score, 75)

    def test_get_trust_score_not_exist(self):
        score = AsnScoreService.get_trust_score("99999")
        self.assertEqual(score, 0)
        config = AsnTrustConfig.objects.get(asn_number="99999")
        self.assertEqual(config.score, 0)

    @patch("asn.services.socket.socket")
    def test_lookup_asn_success(self, mock_socket_cls):
        mock_socket = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_socket
        whois_response = b"AS | IP | Country | Desc\n15169 | 8.8.8.8 | US | GOOGLE\n"
        mock_socket.recv.side_effect = [whois_response, b""]
        record = AsnScoreService.lookup_asn("8.8.8.8")
        self.assertEqual(record.ip_address, "8.8.8.8")
        self.assertEqual(record.asn_number, "15169")
        self.assertEqual(record.asn_description, "GOOGLE")
        self.assertEqual(record.trust_score, 0)

    @patch("asn.services.socket.socket")
    def test_lookup_asn_failure(self, mock_socket_cls):
        mock_socket = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_socket
        mock_socket.connect.side_effect = Exception("Connection failed")
        record = AsnScoreService.lookup_asn("1.2.3.4")
        self.assertEqual(record.asn_number, "UNKNOWN")
        self.assertIn("Connection failed", record.asn_description)
        self.assertEqual(record.trust_score, 0)
