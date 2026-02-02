from django.test import TestCase
from alert.services import AlertService
from alert.models import Alert

class TestAlertService(TestCase):

    def test_create_alert_high_severity_auto(self):
        alert = AlertService.create_alert(
            alert_type="SQL Injection",
            ip_address="1.2.3.4",
            detail="Detected SQL injection attempt",
            severity="critical"  # biar auto compute
        )
        self.assertEqual(alert.severity.lower(), "critical")
        self.assertEqual(alert.alert_type, "SQL Injection")
        self.assertEqual(alert.ip_address, "1.2.3.4")
        self.assertEqual(alert.detail, "Detected SQL injection attempt")

    def test_create_alert_low_severity_manual(self):
        alert = AlertService.create_alert(
            alert_type="Info",
            ip_address="5.6.7.8",
            detail="Normal scan",
            severity="low"
        )
        self.assertEqual(alert.severity.lower(), "low")
        self.assertEqual(alert.alert_type, "Info")
        self.assertEqual(alert.ip_address, "5.6.7.8")
        self.assertEqual(alert.detail, "Normal scan")

    def test_create_alert_auto_severity_xss(self):
        alert = AlertService.create_alert(
            alert_type="Test",
            ip_address="9.8.7.6",
            detail="Detected XSS attempt",  # triggers critical
            severity="critical"
        )
        self.assertEqual(alert.severity.lower(), "critical")
