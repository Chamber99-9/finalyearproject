"""Background EMI-reminder scheduler.

Runs ``process_due_reminders`` on a fixed interval so customers are emailed ~7
days before each EMI due date automatically, without an admin having to trigger
the billing job. The reminder itself is idempotent per installment, so repeated
runs never send a customer the same reminder twice.

Only reminders are run here — overdue counting and blacklisting stay behind the
explicit admin "Run billing" action so nothing is auto-penalised in the
background.
"""

import asyncio
import logging

from app.config import get_settings

logger = logging.getLogger("sajilo.reminders")


async def _reminder_loop(interval_seconds: int) -> None:
    from app.database import get_database
    from app.services.loan_account_service import process_due_reminders

    while True:
        try:
            result = await process_due_reminders(get_database())
            if result.get("reminded"):
                logger.info("EMI reminders sent: %s", result["reminded"])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - never let a bad run kill the loop
            logger.exception("EMI reminder run failed")
        await asyncio.sleep(interval_seconds)


def start_reminder_scheduler() -> asyncio.Task | None:
    """Start the periodic reminder loop; returns the task (or None if disabled)."""
    settings = get_settings()
    if not settings.reminder_scheduler_enabled:
        return None
    interval_seconds = max(int(settings.reminder_scheduler_interval_hours), 1) * 3600
    logger.info(
        "Starting EMI reminder scheduler (every %sh, %s days before due).",
        settings.reminder_scheduler_interval_hours,
        settings.reminder_days_before,
    )
    return asyncio.create_task(_reminder_loop(interval_seconds))
