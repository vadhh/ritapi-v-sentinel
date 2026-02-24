import requests
import os
import logging
import html

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def escape(text):
    return html.escape(str(text))


def send_telegram_message(alert_type: str, client_ip: str, severity: str, reason: str):
    logger.debug("Sending Telegram alert...")
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.warning("Telegram token or chat ID not configured.")
        return  # fail silently, avoids crashing alert system
    text = (
        f"🚨 <b>Security Alert: {escape(alert_type)}</b>\n"
        f"IP: <code>{escape(client_ip)}</code>\n"
        f"Severity: <b>{escape(severity)}</b>\n"
        f"Reason: {escape(reason)}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        logger.exception("Failed to send Telegram message")
