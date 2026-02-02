from django.test import TestCase
from alert.models import Alert

class TestAlertModels(TestCase):

    def test_alert_str(self):
        alert = Alert(alert_type="XSS", ip_address="1.2.3.4", detail="Detected XSS", severity="critical")
        self.assertEqual(str(alert), "[CRITICAL] XSS - 1.2.3.4")
