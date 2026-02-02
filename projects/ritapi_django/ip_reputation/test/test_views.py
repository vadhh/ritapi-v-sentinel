from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

class TestIpReputationViewsMock(TestCase):

    def setUp(self):
        self.client = APIClient()

    @patch('ip_reputation.services.IpReputationService.check_reputation')
    def test_lookup_post_mocked(self, mock_check):
        mock_check.return_value = MagicMock(
            id=1,
            ip_address='23.137.248.100',
            reputation_score=-2,
            isp='Test ISP',
            country='Test Country',
            is_tor=True,
            scores={"sources": ["TOR"], "ip_reputation_score": -2},
            timestamp='2025-12-11T08:00:00Z'
        )

        response = self.client.post(
            '/ip-reputation/lookup/',
            {'ip': '23.137.248.100'},
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ip_address'], '23.137.248.100')
        self.assertTrue(response.data['is_tor'])
        self.assertIn('TOR', response.data['sources'])
        self.assertTrue(response.data['malicious'])

    def test_lookup_missing_ip(self):
        response = self.client.post('/ip-reputation/lookup/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], "The 'ip' parameter is required")
