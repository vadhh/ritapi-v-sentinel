# ip_reputation/services.py

import logging
import requests
from django.utils import timezone
from .models import IpReputation, InternalIPList

logger = logging.getLogger(__name__)

class IpReputationService:
    TOR_URL = "https://check.torproject.org/torbulkexitlist"
    FIREHOL_URL = "https://iplists.firehol.org/files/firehol_level1.netset"
    EMERGING_URL = "https://rules.emergingthreats.net/blockrules/compromised-ips.txt"

    tor_list = set()
    firehol_list = set()
    emerging_list = set()
    feeds_loaded = False

    @classmethod
    def load_threat_feeds(cls):
        def load_feed(url):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    lines = resp.text.strip().splitlines()
                    return set(line.strip() for line in lines if line and not line.startswith("#"))
            except Exception as e:
                logger.error("Error loading feed %s: %s", url, e)
            return set()

        if not cls.feeds_loaded:
            cls.tor_list = load_feed(cls.TOR_URL)
            cls.firehol_list = load_feed(cls.FIREHOL_URL)
            cls.emerging_list = load_feed(cls.EMERGING_URL)
            cls.feeds_loaded = True

    @staticmethod
    # Perubahan: Hapus parameter service_id yang tidak digunakan
    def check_reputation(ip_address: str): 
        try:
            IpReputationService.load_threat_feeds()

            # === Internal allow/deny override check ===
            now = timezone.now()
            # Perubahan: Hapus filter yang berhubungan dengan service
            overrides = InternalIPList.objects.filter(
                ip_address=ip_address
            ).order_by("-created_at") # Tambahkan ordering agar konsisten mengambil yang terbaru/terdahulu

            for override in overrides:
                if override.expires_at and override.expires_at < now:
                    continue  # skip expired

                if override.list_type == "allow":
                    reputation_score = 10
                    sources = ["INTERNAL_ALLOW"]
                    is_tor = False
                    isp, country, asn = "INTERNAL", "INTERNAL", "INTERNAL"
                    break

                elif override.list_type == "deny":
                    reputation_score = -10
                    sources = ["INTERNAL_DENY"]
                    is_tor = False
                    isp, country, asn = "INTERNAL", "INTERNAL", "INTERNAL"
                    break
            else:
                # === External IP data and threat feeds ===
                url = f"https://ipapi.co/{ip_address}/json/"
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    raise Exception(f"API Error {resp.status_code}")

                data = resp.json()
                isp = data.get("org", "UNKNOWN")
                country = data.get("country_name", "UNKNOWN")
                asn = data.get("asn", "")

                reputation_score = 0
                is_tor = False
                sources = []

                # Example hardcoded allowlist
                allowlist = ["1.1.1.1"]
                if ip_address in allowlist:
                    reputation_score += 1
                    sources.append("ALLOWLIST")

                if ip_address in IpReputationService.tor_list:
                    reputation_score -= 2
                    is_tor = True
                    sources.append("TOR")

                if ip_address in IpReputationService.emerging_list:
                    reputation_score -= 3
                    sources.append("EMERGING_THREATS")

                if ip_address in IpReputationService.firehol_list:
                    reputation_score -= 5
                    sources.append("FIREHOL")

            scores = {
                "isp": isp,
                "country": country,
                "asn": asn,
                "is_tor": is_tor,
                "ip_reputation_score": reputation_score,
                "sources": sources,
            }

        except Exception as e:
            isp, country, asn, is_tor = "UNKNOWN", "UNKNOWN", "UNKNOWN", False
            reputation_score = 0
            sources = []
            scores = {"error": str(e)}

        # ✅ simpan ke DB
        record, created = IpReputation.objects.update_or_create(
            ip_address=ip_address,
            defaults={
                "scores": scores,
                "reputation_score": reputation_score,
                "isp": isp,
                "country": country,
                "is_tor": is_tor,
                "timestamp": timezone.now(),
            }
        )
        return record