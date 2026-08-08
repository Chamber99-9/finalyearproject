"""Loan account lifecycle: creation on approval, payments, reminders, blacklist."""

from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.config import get_settings
from app.models.loan_account import (
    LoanAccountStatus,
    add_one_month,
    create_loan_account_document,
    loan_account_id_to_str,
)
from app.services.clock_service import simulated_now
from app.services.email_service import send_email
from app.services.notification_service import create_notification

LOAN_ACCOUNTS_COLLECTION = "loan_accounts"
USERS_COLLECTION = "users"


class LoanAccountNotFoundError(Exception):
    pass


class LoanAccountStatusError(Exception):
    pass


def serialize_loan_account(document: dict[str, Any]) -> dict[str, Any]:
    return loan_account_id_to_str(document)


async def create_loan_account_for_application(
    database: AsyncIOMotorDatabase,
    application: dict[str, Any],
) -> dict[str, Any] | None:
    """Create a loan account from an approved application (idempotent)."""
    application_id = str(application.get("_id") or application.get("id"))
    existing = await database[LOAN_ACCOUNTS_COLLECTION].find_one(
        {"application_id": application_id}
    )
    if existing is not None:
        return existing

    principal = application.get("requested_loan_amount")
    monthly_emi = application.get("monthly_emi")
    tenure_months = application.get("loan_duration_months")
    if not principal or not monthly_emi or not tenure_months:
        # Application isn't complete enough to disburse; skip silently.
        return None

    document = create_loan_account_document(
        application_id=application_id,
        applicant_id=str(application.get("applicant_id")),
        principal=float(principal),
        interest_rate=float(application.get("interest_rate_used") or 0),
        tenure_months=int(tenure_months),
        monthly_emi=float(monthly_emi),
        total_payment=float(application.get("total_payment") or monthly_emi * tenure_months),
        total_interest=float(application.get("total_interest") or 0),
    )
    result = await database[LOAN_ACCOUNTS_COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def list_customer_loans(
    database: AsyncIOMotorDatabase,
    applicant_id: str,
) -> list[dict[str, Any]]:
    cursor = database[LOAN_ACCOUNTS_COLLECTION].find(
        {"applicant_id": applicant_id}
    ).sort("created_at", -1)
    return [document async for document in cursor]


async def record_payment(
    database: AsyncIOMotorDatabase,
    loan_id: str,
    applicant_id: str,
    verified_amount: float | None = None,
) -> dict[str, Any]:
    """Record one EMI payment: reduce the outstanding balance and advance the due date.

    ``verified_amount`` is the amount an officer verified was actually deposited
    (from the bank receipt). When omitted, the full ``monthly_emi`` is assumed
    (legacy/gateway-confirmed payments, where the rail already guarantees the
    exact amount was collected).

    A deposit that covers at least the monthly EMI clears one installment and
    rolls the due date forward as before. A deposit that falls short is applied
    as a **partial payment**: the outstanding balance drops by what was actually
    received, but the installment count and due date do not move — the customer
    still owes the shortfall before the EMI is considered paid.
    """
    if not ObjectId.is_valid(loan_id):
        raise LoanAccountNotFoundError

    loan = await database[LOAN_ACCOUNTS_COLLECTION].find_one(
        {"_id": ObjectId(loan_id), "applicant_id": applicant_id}
    )
    if loan is None:
        raise LoanAccountNotFoundError
    if loan.get("status") != LoanAccountStatus.ACTIVE.value:
        raise LoanAccountStatusError

    monthly_emi = float(loan.get("monthly_emi") or 0)
    outstanding = float(loan.get("outstanding_balance") or 0)
    deposit = monthly_emi if verified_amount is None else max(float(verified_amount), 0.0)
    amount_paid = round(min(deposit, outstanding), 2)
    new_outstanding = round(outstanding - amount_paid, 2)
    installments_total = int(loan.get("installments_total", 0))

    # A cent of rounding slack so a deposit equal to the EMI (float arithmetic)
    # still counts as a full installment rather than a fractional shortfall.
    covers_installment = amount_paid + 0.01 >= monthly_emi or new_outstanding <= 0
    installments_paid = int(loan.get("installments_paid", 0)) + (1 if covers_installment else 0)

    updates: dict[str, Any] = {
        "outstanding_balance": max(new_outstanding, 0.0),
        "installments_paid": installments_paid,
        "updated_at": datetime.now(UTC),
    }
    if covers_installment:
        updates["missed_installments"] = 0
        updates["next_due_date"] = (
            add_one_month(loan["next_due_date"])
            if isinstance(loan.get("next_due_date"), datetime)
            else None
        )
    if installments_paid >= installments_total or new_outstanding <= 0:
        updates["status"] = LoanAccountStatus.COMPLETED.value
        updates["outstanding_balance"] = 0.0

    updated = await database[LOAN_ACCOUNTS_COLLECTION].find_one_and_update(
        {"_id": loan["_id"]},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise LoanAccountNotFoundError
    updated["_last_payment"] = amount_paid
    updated["_is_partial"] = not covers_installment
    updated["_shortfall"] = round(max(monthly_emi - amount_paid, 0.0), 2) if not covers_installment else 0.0
    return updated


async def record_prepayment(
    database: AsyncIOMotorDatabase,
    loan_id: str,
    applicant_id: str,
    principal_amount: float,
) -> dict[str, Any]:
    """Apply an advance lump-sum payment: reduce the outstanding balance directly.

    Only the principal portion (``principal_amount``) reduces the balance — any
    bank/extra fee is charged on top and does not reduce what is owed. Regular
    EMIs continue on the (now smaller) balance until it clears.
    """
    if not ObjectId.is_valid(loan_id):
        raise LoanAccountNotFoundError

    loan = await database[LOAN_ACCOUNTS_COLLECTION].find_one(
        {"_id": ObjectId(loan_id), "applicant_id": applicant_id}
    )
    if loan is None:
        raise LoanAccountNotFoundError
    if loan.get("status") != LoanAccountStatus.ACTIVE.value:
        raise LoanAccountStatusError

    outstanding = float(loan.get("outstanding_balance") or 0)
    amount = round(min(float(principal_amount), outstanding), 2)
    new_outstanding = round(outstanding - amount, 2)
    updates: dict[str, Any] = {
        "outstanding_balance": max(new_outstanding, 0.0),
        "updated_at": datetime.now(UTC),
    }
    if new_outstanding <= 0:
        updates["status"] = LoanAccountStatus.COMPLETED.value
        updates["outstanding_balance"] = 0.0
        updates["installments_paid"] = int(loan.get("installments_total", 0))

    updated = await database[LOAN_ACCOUNTS_COLLECTION].find_one_and_update(
        {"_id": loan["_id"]},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise LoanAccountNotFoundError
    updated["_last_payment"] = amount
    return updated


async def process_due_reminders(database: AsyncIOMotorDatabase) -> dict[str, Any]:
    """Email + notify customers whose EMI is due within the reminder window.

    The window is ``reminder_days_before`` days (7 by default), so a customer is
    reminded once their next EMI is 7 days away or nearer, and again for each new
    installment. Idempotent per due date: the same installment is never reminded
    twice, so running the billing job repeatedly does not spam the customer.
    """
    days_before = get_settings().reminder_days_before
    now = await simulated_now(database)
    window_end = now + timedelta(days=days_before)
    reminded = 0
    cursor = database[LOAN_ACCOUNTS_COLLECTION].find(
        {"status": LoanAccountStatus.ACTIVE.value}
    )
    async for loan in cursor:
        due = loan.get("next_due_date")
        if not isinstance(due, datetime):
            continue
        # Mongo may return naive datetimes; compare on the same tz as `now`.
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)

        if not (now <= due <= window_end):
            continue

        # Only remind once per installment (keyed by the due date).
        due_key = due.date().isoformat()
        if loan.get("last_reminder_due_date") == due_key:
            continue

        applicant_id = str(loan.get("applicant_id"))
        emi = loan.get("monthly_emi")
        days_remaining = max((due.date() - now.date()).days, 0)
        when = "today" if days_remaining == 0 else f"in {days_remaining} day(s)"
        title = f"EMI due {when}"
        message = (
            f"Reminder: your EMI of NPR {emi} is due on {due.date()} ({when}). "
            f"Please pay on time to avoid penalties and keep your account in good standing."
        )
        try:
            await create_notification(
                database=database,
                user_id=applicant_id,
                title=title,
                message=message,
            )
        except Exception:  # noqa: BLE001 - reminders are best-effort
            pass

        user = await database[USERS_COLLECTION].find_one(
            {"_id": ObjectId(applicant_id)} if ObjectId.is_valid(applicant_id) else {}
        )
        if user and user.get("email"):
            try:
                await send_email(
                    database=database,
                    to_email=str(user["email"]),
                    subject=f"Sajilo Loan — EMI due {when} ({due.date()})",
                    body=message,
                )
            except Exception:  # noqa: BLE001 - a failed email must never crash billing
                pass

        # Mark this installment as reminded so we don't email it again.
        await database[LOAN_ACCOUNTS_COLLECTION].update_one(
            {"_id": loan["_id"]},
            {"$set": {"last_reminder_due_date": due_key}},
        )
        reminded += 1
    return {"reminded": reminded}


async def process_overdue(database: AsyncIOMotorDatabase) -> dict[str, Any]:
    """Advance overdue loans, count missed installments, and blacklist defaulters."""
    now = await simulated_now(database)
    threshold = get_settings().blacklist_overdue_months
    overdue = 0
    blacklisted = 0
    cursor = database[LOAN_ACCOUNTS_COLLECTION].find(
        {"status": LoanAccountStatus.ACTIVE.value}
    )
    async for loan in cursor:
        due = loan.get("next_due_date")
        if not isinstance(due, datetime) or due >= now:
            continue

        missed = int(loan.get("missed_installments", 0)) + 1
        updates: dict[str, Any] = {
            "missed_installments": missed,
            "next_due_date": add_one_month(due),
            "updated_at": now,
        }
        applicant_id = str(loan.get("applicant_id"))
        if missed >= threshold:
            updates["status"] = LoanAccountStatus.DEFAULTED.value
            if ObjectId.is_valid(applicant_id):
                await database[USERS_COLLECTION].update_one(
                    {"_id": ObjectId(applicant_id)},
                    {"$set": {"is_blacklisted": True}},
                )
                try:
                    await create_notification(
                        database=database,
                        user_id=applicant_id,
                        title="Account blacklisted",
                        message=(
                            "Your account has been blacklisted due to missed EMI "
                            "payments. Please contact the bank."
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass
                blacklisted += 1

        await database[LOAN_ACCOUNTS_COLLECTION].update_one(
            {"_id": loan["_id"]}, {"$set": updates}
        )
        overdue += 1

    return {"overdue": overdue, "blacklisted": blacklisted}
