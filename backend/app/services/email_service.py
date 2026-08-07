"""Email alerts.

When SMTP settings are configured (``smtp_host``), a real email is sent via
stdlib ``smtplib``. Otherwise the message is stored in the ``emails`` collection
and logged, so the flow is fully demonstrable without any credentials. Either
way an email record is persisted for auditability.
"""

import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings

logger = logging.getLogger("sajilo.email")

EMAILS_COLLECTION = "emails"


def _send_via_smtp(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    # Gmail (and most providers) require the From to be the authenticated
    # mailbox. Fall back to smtp_user when no real from-address is configured so
    # the message is accepted instead of silently rejected/rewritten.
    from_address = settings.email_from or settings.smtp_user
    if from_address.endswith("sajiloloan.example") and settings.smtp_user:
        from_address = settings.smtp_user

    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


async def send_email(
    database: AsyncIOMotorDatabase,
    to_email: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send (or simulate) an email and persist a record of it."""
    settings = get_settings()
    delivered = False
    error: str | None = None

    if settings.smtp_host:
        try:
            _send_via_smtp(to_email, subject, body)
            delivered = True
        except Exception as exc:  # noqa: BLE001 - record and continue
            error = str(exc)
            logger.warning("SMTP send failed for %s: %s", to_email, error)
    else:
        # No SMTP configured: log the message so it's visible in dev.
        logger.info("EMAIL (simulated) to %s | %s | %s", to_email, subject, body)

    record = {
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "delivered": delivered,
        "simulated": not settings.smtp_host,
        "error": error,
        "created_at": datetime.now(UTC),
    }
    try:
        await database[EMAILS_COLLECTION].insert_one(dict(record))
    except Exception as exc:  # noqa: BLE001 - non-fatal
        logger.warning("Could not store email record: %s", exc)

    return record
