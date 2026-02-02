from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from blocking.models import BlockedIP

# Path ke service yang akan di-mock (sesuai impor di views.py)
BLOCKING_SERVICE_PATH = 'blocking.views.BlockingService'

class TestBlockingViews(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.ip = "10.0.0.5"

    @patch(BLOCKING_SERVICE_PATH + '.block_ip')
    def test_block_ip_view_success(self, mock_block_ip):
        """Test POST /block/ untuk blokir IP sukses."""
        # Mock return object
        mock_blocked_ip = MagicMock(id=99, ip_address=self.ip)
        mock_block_ip.return_value = mock_blocked_ip

        data = {
            "ip_address": self.ip,
            "reason": "Test View Block",
            "severity": "high",
            "duration_minutes": 10
        }
        
        response = self.client.post('/blocking/block/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'IP blocked')
        self.assertEqual(response.data['id'], 99)
        
        # Verifikasi service dipanggil dengan benar
        mock_block_ip.assert_called_once_with(
            ip_address=self.ip,
            reason="Test View Block",
            severity="high",
            duration_minutes=10
        )

    @patch(BLOCKING_SERVICE_PATH + '.unblock_ip')
    def test_unblock_ip_view_success(self, mock_unblock_ip):
        """Test POST /unblock/ untuk lepas blokir IP sukses."""
        # Mock return object
        mock_unblock_ip.return_value = MagicMock(ip_address=self.ip, active=False)

        data = {"ip_address": self.ip}
        
        response = self.client.post('/blocking/unblock/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], f"IP {self.ip} unblocked")
        mock_unblock_ip.assert_called_once_with(self.ip)

    @patch(BLOCKING_SERVICE_PATH + '.unblock_ip')
    def test_unblock_ip_view_not_found(self, mock_unblock_ip):
        """Test POST /unblock/ ketika IP tidak ditemukan."""
        mock_unblock_ip.return_value = None

        data = {"ip_address": "99.99.99.99"}
        
        response = self.client.post('/blocking/unblock/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    @patch(BLOCKING_SERVICE_PATH + '.is_blocked')
    def test_check_ip_view_blocked(self, mock_is_blocked):
        """Test GET /check/<ip>/ ketika IP diblokir."""
        mock_is_blocked.return_value = True
        
        response = self.client.get(f'/blocking/check/{self.ip}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['blocked'])
        self.assertEqual(response.data['ip_address'], self.ip)
        mock_is_blocked.assert_called_once_with(self.ip)

    def test_list_blocked_ips_view(self):
        """Test GET /blocked/ untuk daftar IP yang diblokir (menggunakan data nyata)."""
        # Buat objek BlockedIP nyata di test DB
        BlockedIP.objects.create(ip_address="1.1.1.1", reason="Test 1", severity="high", active=True)
        BlockedIP.objects.create(ip_address="2.2.2.2", reason="Test 2", severity="low", active=False) # Harus diabaikan
        BlockedIP.objects.create(ip_address="3.3.3.3", reason="Test 3", severity="critical", active=True)
        
        response = self.client.get('/blocking/blocked/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 2) # Hanya 2 yang aktif
        
        # Cek apakah field yang relevan ada di respons
        first_entry = response.data[0]
        self.assertIn('ip_address', first_entry)
        self.assertIn('reason', first_entry)
        self.assertTrue(first_entry['active'])
        
        # Karena diurutkan berdasarkan -blocked_at, 3.3.3.3 (yang dibuat terakhir) harusnya pertama
        self.assertEqual(first_entry['ip_address'], '3.3.3.3')