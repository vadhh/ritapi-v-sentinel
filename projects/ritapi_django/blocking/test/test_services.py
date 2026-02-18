from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import datetime, timedelta, timezone as dt_timezone
from blocking.services import BlockingService
from blocking.models import BlockedIP

# Path untuk fungsi/kelas yang akan di-mock
TIMEZONE_NOW_PATH = 'blocking.services.timezone.now'
GEOLITE2_PATH = 'blocking.services.geoip2.database.Reader'

class TestBlockingService(TestCase):

    def setUp(self):
        self.mock_now = datetime(2025, 12, 11, 10, 0, 0, tzinfo=dt_timezone.utc)
        self.mock_future = self.mock_now + timedelta(minutes=30)
        self.ip = "8.8.8.8"

    def mock_geoip2_success(self, mock_reader):
        """Helper untuk mensimulasikan lookup GeoIP sukses."""
        mock_response = MagicMock()
        mock_response.country.iso_code = "US"
        mock_response.country.name = "United States"
        mock_response.location.latitude = 37.751
        mock_response.location.longitude = -97.822
        mock_reader.return_value.__enter__.return_value.city.return_value = mock_response

    def mock_geoip2_failure(self, mock_reader):
        """Helper untuk mensimulasikan lookup GeoIP gagal."""
        mock_reader.return_value.__enter__.return_value.city.side_effect = Exception("GeoIP failed")

    @patch(GEOLITE2_PATH)
    @patch(TIMEZONE_NOW_PATH, autospec=True)
    def test_block_ip_permanent_success(self, mock_now, mock_reader):
        """Test blokir IP permanen dengan data geoip sukses."""
        self.mock_geoip2_success(mock_reader)
        mock_now.return_value = self.mock_now

        blocked = BlockingService.block_ip(
            ip_address=self.ip,
            reason="Test Block Permanent",
            severity="critical",
            duration_minutes=None
        )

        self.assertTrue(blocked.active)
        self.assertEqual(blocked.ip_address, self.ip)
        self.assertEqual(blocked.severity, "critical")
        self.assertIsNone(blocked.expires_at)
        self.assertEqual(blocked.country, "US")
        self.assertEqual(blocked.latitude, 37.751)

    @patch(GEOLITE2_PATH)
    @patch(TIMEZONE_NOW_PATH, autospec=True)
    def test_block_ip_temporary_geoip_failure(self, mock_now, mock_reader):
        """Test blokir temporer dengan GeoIP gagal."""
        self.mock_geoip2_failure(mock_reader)
        mock_now.return_value = self.mock_now

        blocked = BlockingService.block_ip(
            ip_address=self.ip,
            reason="Test Block Temporary",
            duration_minutes=30
        )
        
        self.assertTrue(blocked.active)
        self.assertIsNotNone(blocked.expires_at)
        # expires_at harus dihitung: self.mock_now + 30 menit
        self.assertEqual(blocked.expires_at, self.mock_now + timedelta(minutes=30))
        # Pastikan data geo kosong
        self.assertIsNone(blocked.country)
        self.assertIsNone(blocked.latitude)
        
    def test_unblock_ip_success(self):
        """Test unblock IP yang ada."""
        BlockedIP.objects.create(ip_address=self.ip, reason="Test", active=True)
        
        unblocked = BlockingService.unblock_ip(self.ip)
        
        self.assertFalse(unblocked.active)
        self.assertEqual(unblocked.ip_address, self.ip)
        
    def test_unblock_ip_not_found(self):
        """Test unblock IP yang tidak ada."""
        unblocked = BlockingService.unblock_ip("99.99.99.99")
        self.assertIsNone(unblocked)

    @patch(TIMEZONE_NOW_PATH, autospec=True)
    def test_is_blocked_active(self, mock_now):
        """Test is_blocked() untuk IP yang aktif diblokir."""
        mock_now.return_value = self.mock_now
        BlockedIP.objects.create(ip_address=self.ip, reason="Test", active=True)
        
        self.assertTrue(BlockingService.is_blocked(self.ip))

    @patch(TIMEZONE_NOW_PATH, autospec=True)
    def test_is_blocked_expired_auto_unblock(self, mock_now):
        """Test is_blocked() untuk IP yang expired (harus auto-unblock)."""
        expired_time = self.mock_now - timedelta(minutes=1)
        mock_now.return_value = self.mock_now
        
        BlockedIP.objects.create(
            ip_address=self.ip, 
            reason="Expired", 
            active=True,
            expires_at=expired_time
        )
        
        # is_blocked harus mengembalikan False
        self.assertFalse(BlockingService.is_blocked(self.ip))
        
        # Cek database, harus sudah jadi active=False
        blocked_db = BlockedIP.objects.get(ip_address=self.ip)
        self.assertFalse(blocked_db.active)