import logging
from django.conf import settings
from django.utils import timezone
from .models import BlockedIP
from datetime import timedelta
import geoip2.database


logger = logging.getLogger("alerts")


class BlockingService:
    @staticmethod
    def block_ip(ip_address: str, reason: str, severity: str = "low", duration_minutes: int = None):
        """
        Blocks an IP address. If duration_minutes is provided, sets an expiration time.
        """
        expires_at = None
        if duration_minutes:
            expires_at = timezone.now() + timedelta(minutes=duration_minutes)
        
        country = None
        country_name = None
        latitude = None
        longitude = None
        
        # Geolocation lookup using GeoLite2 City DB
        db_path_city = getattr(settings, "GEOLITE2_CITY_DB", "/usr/share/GeoIP/GeoLite2-City.mmdb")
        
        try:
            with geoip2.database.Reader(db_path_city) as reader:
                response = reader.city(ip_address)
                country = response.country.iso_code
                country_name = response.country.name
                latitude = response.location.latitude
                longitude = response.location.longitude
        except Exception as e:
            logger.debug(f"GeoLite2 lookup failed for {ip_address}: {e}")

        # Create or update the BlockedIP entry
        blocked, created = BlockedIP.objects.update_or_create(
            ip_address=ip_address,
            defaults={
                "reason": reason,
                "severity": severity,
                "active": True,
                "expires_at": expires_at,
                "country": country,
                "country_name": country_name,
                "latitude": latitude,
                "longitude": longitude,
                "blocked_at": timezone.now(),
            },
        )
        return blocked

    @staticmethod
    def unblock_ip(ip_address: str):
        """
        Removes an IP block (sets active=False).
        """
        try:
            blocked = BlockedIP.objects.get(ip_address=ip_address)
            blocked.active = False
            blocked.save()
            return blocked
        except BlockedIP.DoesNotExist:
            return None

    @staticmethod
    def is_blocked(ip_address: str):
        """
        Checks if the IP is currently blocked (and not expired).
        """
        try:
            blocked = BlockedIP.objects.get(ip_address=ip_address, active=True)
            if blocked.expires_at and blocked.expires_at < timezone.now():
                # auto unblock if expired
                blocked.active = False
                blocked.save()
                return False
            return True
        except BlockedIP.DoesNotExist:
            return False
        
    @staticmethod
    def soft_block_ip(ip_address: str, reason: str, severity: str = "medium"):
        """
        Soft block: only marks the IP with active=False.
        This does not actually block requests, but logs the entry.
        """
        blocked, created = BlockedIP.objects.update_or_create(
            ip_address=ip_address,
            defaults={
                "reason": reason,
                "severity": severity,
                "active": False,   # ✅ The difference is here
                "expires_at": None,
            },
        )
        return blocked