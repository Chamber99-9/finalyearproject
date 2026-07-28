"""Loan account (disbursed loan) model.

Created when an application is approved. Tracks the outstanding balance, which
reduces after each EMI payment, the next due date (10th of each month), and the
missed-installment counter used for blacklisting.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId

from app.config import get_settings


class LoanAccountStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"


def next_due_date(reference: date | None = None) -> datetime:
    """Return the next EMI due date — the configured due day of next month."""
    due_day = get_settings().emi_due_day
    today = reference or datetime.now(UTC).date()
    # Move to next month's due day.
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    return datetime(year, month, min(due_day, 28), tzinfo=UTC)


def add_one_month(reference: datetime) -> datetime:
    year = reference.year + (1 if reference.month == 12 else 0)
    month = 1 if reference.month == 12 else reference.month + 1
    return reference.replace(year=year, month=month)


def create_loan_account_document(
    *,
    application_id: str,
    applicant_id: str,
    principal: float,
    interest_rate: float,
    tenure_months: int,
    monthly_emi: float,
    total_payment: float,
    total_interest: float,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "application_id": application_id,
        "applicant_id": applicant_id,
        "principal": float(principal),
        "interest_rate": float(interest_rate),
        "tenure_months": int(tenure_months),
        "monthly_emi": float(monthly_emi),
        "total_payment": float(total_payment),
        "total_interest": float(total_interest),
        "outstanding_balance": float(total_payment),
        "installments_paid": 0,
        "installments_total": int(tenure_months),
        "missed_installments": 0,
        "next_due_date": next_due_date(),
        "status": LoanAccountStatus.ACTIVE.value,
        "created_at": now,
        "updated_at": now,
    }


def loan_account_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document
