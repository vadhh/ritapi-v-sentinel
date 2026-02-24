# asn/tests/test_models.py
from django.test import TestCase
from asn.models import AsnTrustConfig, AsnInfo


class TestAsnModels(TestCase):

    def test_asn_trust_config_creation(self):
        config = AsnTrustConfig.objects.create(
            asn_number="123", name="Test ASN", score=50
        )
        self.assertEqual(config.asn_number, "123")
        self.assertEqual(config.score, 50)

    def test_asn_info_creation(self):
        info = AsnInfo.objects.create(
            ip_address="1.2.3.4",
            asn_number="123",
            asn_description="TEST",
            trust_score=50,
            is_latest=True,
        )
        self.assertEqual(info.ip_address, "1.2.3.4")
        self.assertTrue(info.is_latest)
