"""Notification Service.

Every notification is stored in-app. SMS / email / push are simulated by default
(logged to the console) so the demo needs no paid provider. Set SMTP_HOST,
SMTP_USER, SMTP_PASS to send real emails. Failures are caught and recorded,
never crashing the request flow.
"""
import logging
import os
import smtplib
from email.message import EmailMessage
from sqlalchemy.orm import Session

from models import Notification, User

log = logging.getLogger("notifications")


def _send_email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        log.info("[EMAIL simulated] to=%s | %s", to, subject)
        return True
    try:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, os.getenv("SMTP_FROM", os.getenv("SMTP_USER")), to
        msg.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as s:
            s.starttls()
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001 - notification failure must not break the flow
        log.warning("Email to %s failed: %s", to, e)
        return False


def _send_sms(phone: str, body: str) -> bool:
    log.info("[SMS simulated] to=%s | %s", phone, body[:120])
    return True


def notify(db: Session, user: User, title: str, body: str, request_id: int | None = None,
           urgent: bool = False) -> Notification:
    channels = ["in_app", "push", "email"] + (["sms"] if urgent else [])
    ok = True
    if "email" in channels:
        ok = _send_email(user.email, title, body) and ok
    if "sms" in channels:
        ok = _send_sms(user.phone, f"{title}\n{body}") and ok
    n = Notification(user_id=user.id, request_id=request_id, title=title, body=body,
                     channels=",".join(channels), delivery_status="sent" if ok else "partial_failure")
    db.add(n)
    return n
