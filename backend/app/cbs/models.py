"""CBS document builders and enums (Customer Account + Loan Account modules)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AccountType(StrEnum):
    SAVINGS = "savings"
    CURRENT = "current"


class DepositAccountStatus(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    CLOSED = "closed"


class CbsLoanAccountStatus(StrEnum):
    # Only PENDING_DISBURSEMENT is reachable in this slice; the rest are the
    # lifecycle the disbursement/EMI features will drive later.
    PENDING_DISBURSEMENT = "pending_disbursement"
    ACTIVE = "active"
    OVERDUE = "overdue"
    CLOSED = "closed"
    WRITTEN_OFF = "written_off"


# GL control accounts these sub-ledgers post into once the ledger feature lands.
DEPOSIT_GL_CODE = "2100"  # Customer Deposits (liability)
LOAN_GL_CODE = "1200"  # Loans & Advances (asset)


def create_cif_document(
    *,
    cif_no: str,
    los_user_id: str,
    full_name: str,
    citizenship_no: str | None = None,
    pan: str | None = None,
    phone: str | None = None,
    kyc_status: str = "not_started",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "cif_no": cif_no,
        "los_user_id": los_user_id,
        "full_name": full_name.strip(),
        "citizenship_no": citizenship_no,
        "pan": pan,
        "phone": phone,
        "kyc_status": kyc_status,
        "created_at": now,
        "updated_at": now,
    }


def create_deposit_account_document(
    *,
    account_no: str,
    cif_no: str,
    account_type: str,
    currency: str,
    gl_code: str = DEPOSIT_GL_CODE,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "account_no": account_no,
        "cif_no": cif_no,
        "account_type": account_type,
        "currency": currency,
        "gl_code": gl_code,
        "balance": 0.0,
        "status": DepositAccountStatus.ACTIVE.value,
        "opened_at": now,
        "updated_at": now,
    }


def create_loan_account_document(
    *,
    loan_account_no: str,
    cif_no: str,
    product_code: str,
    los_application_id: str,
    sanction_amount: float,
    interest_rate: float,
    tenure_months: int,
    emi_amount: float,
    disbursement_account_no: str,
    currency: str,
    gl_code: str = LOAN_GL_CODE,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "loan_account_no": loan_account_no,
        "cif_no": cif_no,
        "product_code": product_code,
        "los_application_id": los_application_id,
        "sanction_amount": float(sanction_amount),
        "interest_rate": float(interest_rate),
        "tenure_months": int(tenure_months),
        "emi_amount": float(emi_amount),
        "disbursement_account_no": disbursement_account_no,
        "currency": currency,
        "gl_code": gl_code,
        # Set at disbursement; pre-disbursement the customer owes nothing yet.
        "principal_outstanding": 0.0,
        "installments_total": int(tenure_months),
        "installments_paid": 0,
        "status": CbsLoanAccountStatus.PENDING_DISBURSEMENT.value,
        "disbursed_at": None,
        "closed_at": None,
        "created_at": now,
        "updated_at": now,
    }


def strip_id(document: dict[str, Any]) -> dict[str, Any]:
    """CBS records are keyed by business numbers, not Mongo ``_id``."""
    document = dict(document)
    document.pop("_id", None)
    return document
