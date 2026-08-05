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
) -> dict[str, Any]:
    """Record one EMI payment: reduce the outstanding balance and advance the due date."""
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
    amount_paid = round(min(monthly_emi, outstanding), 2)
    new_outstanding = round(outstanding - amount_paid, 2)
    installments_paid = int(loan.get("installments_paid", 0)) + 1
    installments_total = int(loan.get("installments_total", 0))

    updates: dict[str, Any] = {
        "outstanding_balance": max(new_outstanding, 0.0),
        "installments_paid": installments_paid,
        "missed_installments": 0,
        "next_due_date": add_one_month(loan["next_due_date"])
        if isinstance(loan.get("next_due_date"), datetime)
        else None,
        "updated_at": datetime.now(UTC),
    }
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
    """Notify + email customers whose EMI is due within the reminder window."""
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
        if now <= due <= window_end:
            applicant_id = str(loan.get("applicant_id"))
            emi = loan.get("monthly_emi")
            message = (
                f"Your EMI of {emi} is due on {due.date()}. "
                f"Please pay within {days_before} days to avoid penalties."
            )
            try:
                await create_notification(
                    database=database,
                    user_id=applicant_id,
                    title="EMI due in 2 days",
                    message=message,
                )
            except Exception:  # noqa: BLE001 - reminders are best-effort
                pass
            user = await database[USERS_COLLECTION].find_one(
                {"_id": ObjectId(applicant_id)} if ObjectId.is_valid(applicant_id) else {}
            )
            if user and user.get("email"):
                await send_email(
                    database=database,
                    to_email=str(user["email"]),
                    subject="Sajilo Loan — EMI due in 2 days",
                    body=message,
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
