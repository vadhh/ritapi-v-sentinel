import logging
from django.conf import settings
from django.core.mail import send_mail, BadHeaderError
from .models import Alert
from utils.telegram_notif import send_telegram_message

logger = logging.getLogger("alerts")


class AlertService:
    @staticmethod
    def create_alert(
        alert_type: str, ip_address: str, detail: str, severity: str = None
    ):
        """
        Buat alert baru dan kirim email notifikasi jika severity tinggi.
        """

        alert = Alert.objects.create(
            alert_type=alert_type,
            ip_address=ip_address,
            detail=detail,
            severity=severity,
        )

        # Kirim email hanya jika severity high atau critical
        if severity and severity.lower() in ["high", "critical"]:
            subject = f"[{severity.upper()}] Alert: {alert_type}"
            message = f"""
            Alert Detected!

            Type     : {alert_type}
            IP       : {ip_address}
            Severity : {severity}
            Detail   : {detail}
            Time     : {alert.timestamp}
            """

            try:
                send_mail(
                    subject,
                    message,
                    getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@waf.local"),
                    [getattr(settings, "ALERT_EMAIL_TO", "admin@example.com")],
                    fail_silently=False,
                )
            except BadHeaderError as e:
                logger.error("Invalid header in alert email: %s", str(e), exc_info=True)
            except Exception as e:
                logger.exception("Error sending alert email: %s", str(e))

        else:
            if severity:
                logger.info(
                    "Alert severity '%s' below threshold; email not sent.", severity
                )
        try:
            result = send_telegram_message(alert_type, ip_address, severity, detail)
            logger.info("Telegram notification sent: %s", result)
        except Exception:
            logger.exception("Failed to send Telegram alert")
        return alert
