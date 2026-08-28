"""Sends a generated report out over email (SMTP) or Telegram."""
import smtplib
from email.message import EmailMessage

import requests

from app.config import settings


class DeliveryNotConfigured(RuntimeError):
    pass


def send_email(pdf_bytes: bytes, summary: dict, filename: str = "report.pdf") -> None:
    if not (settings.smtp_host and settings.smtp_from and settings.report_email_to):
        raise DeliveryNotConfigured("Set SMTP_HOST, SMTP_FROM, and REPORT_EMAIL_TO to enable email delivery.")

    msg = EmailMessage()
    msg["Subject"] = f"Infrastructure report - {summary['critical']} critical, {summary['warning']} warning"
    msg["From"] = settings.smtp_from
    msg["To"] = settings.report_email_to
    msg.set_content(
        f"Total servers: {summary['total_servers']}\n"
        f"Healthy: {summary['healthy']}  Warning: {summary['warning']}  Critical: {summary['critical']}\n\n"
        "Full report attached."
    )
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def send_telegram(pdf_bytes: bytes, summary: dict, filename: str = "report.pdf") -> None:
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        raise DeliveryNotConfigured("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable Telegram delivery.")

    caption = (
        f"Infrastructure report: {summary['total_servers']} servers - "
        f"{summary['healthy']} healthy, {summary['warning']} warning, {summary['critical']} critical"
    )
    response = requests.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument",
        data={"chat_id": settings.telegram_chat_id, "caption": caption},
        files={"document": (filename, pdf_bytes, "application/pdf")},
        timeout=30,
    )
    response.raise_for_status()
