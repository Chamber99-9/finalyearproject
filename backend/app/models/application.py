from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId

from app.services.emi_service import (
    EMIValidationError,
    TenureUnit,
    calculate_emi,
    compute_affordability,
)


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    DOCUMENT_REQUESTED = "document_requested"
    COUNTER_OFFERED = "counter_offered"
    APPROVED = "approved"
    REJECTED = "rejected"


class LoanType(StrEnum):
    PERSONAL = "personal"
    INSTANT = "instant"
    HOME = "home"
    AUTO = "auto"
    EDUCATION = "education"
    LOAN_AGAINST_SHARES = "loan_against_shares"
    BUSINESS = "business"
    VEHICLE = "vehicle"
    AGRICULTURE = "agriculture"
    OTHER = "other"


class EmploymentType(StrEnum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"
    BUSINESS = "business"
    CONTRACT = "contract"
    UNEMPLOYED = "unemployed"
    OTHER = "other"


class SavingsBuffer(StrEnum):
    GOOD = "good"
    AVERAGE = "average"
    LOW = "low"


class RepaymentHistory(StrEnum):
    NO_PREVIOUS_DEFAULT = "no_previous_default"
    MINOR_LATE_PAYMENT = "minor_late_payment"
    PREVIOUS_DEFAULT = "previous_default"


def compute_emi_fields(
    *,
    requested_loan_amount: Any,
    interest_rate_used: Any,
    loan_duration_months: Any,
    existing_monthly_debt: Any = None,
    monthly_income: Any = None,
) -> dict[str, Any]:
    """Compute EMI + affordability fields for a loan application document.

    ``interest_rate_used`` is the bank-defined rate applied to this application
    (never entered by the customer); it is stored on the document so a later
    change to the bank default never alters existing applications.
    ``loan_duration_months`` is the canonical installment count (N).

    Returns ``{}`` when the required inputs are missing or invalid, so callers
    can safely skip EMI updates for still-incomplete drafts instead of failing.
    When income and existing debt are also available, the EMI-inclusive
    debt-to-income ratio and affordability recommendation are added too:

        interest_rate_used, monthly_emi, total_interest, total_payment,
        emi_dti_ratio, affordability
    """
    if (
        requested_loan_amount in (None, "")
        or interest_rate_used in (None, "")
        or loan_duration_months in (None, "")
    ):
        return {}

    try:
        emi = calculate_emi(
            loan_amount=float(requested_loan_amount),
            annual_interest_rate=float(interest_rate_used),
            tenure=int(loan_duration_months),
            tenure_unit=TenureUnit.MONTHS,
        )
    except (EMIValidationError, TypeError, ValueError):
        return {}

    fields: dict[str, Any] = {
        "interest_rate_used": float(interest_rate_used),
        "monthly_emi": emi["monthly_emi"],
        "total_interest": emi["total_interest"],
        "total_payment": emi["total_payment"],
    }

    if monthly_income not in (None, "") and existing_monthly_debt not in (None, ""):
        try:
            affordability = compute_affordability(
                monthly_emi=emi["monthly_emi"],
                existing_monthly_debt=float(existing_monthly_debt),
                monthly_income=float(monthly_income),
            )
            fields["emi_dti_ratio"] = affordability["dti_ratio"]
            fields["affordability"] = affordability["affordability"]
        except (TypeError, ValueError):
            pass

    return fields


def create_application_document(
    *,
    applicant_id: str,
    payload: Any,
    interest_rate_used: float,
) -> dict[str, Any]:
    """Build a loan application document.

    ``interest_rate_used`` is the bank-defined rate resolved by the caller (from
    loan_settings_service) — the customer never supplies it.
    """
    now = datetime.now(UTC)
    document = {
        "applicant_id": applicant_id,
        "full_name": payload.full_name.strip(),
        "citizenship_number": payload.citizenship_number.strip(),
        "phone": payload.phone.strip(),
        "address": payload.address.strip(),
        "loan_type": payload.loan_type.value,
        "monthly_income": payload.monthly_income,
        "employment_type": payload.employment_type.value,
        "existing_monthly_debt": payload.existing_monthly_debt,
        "requested_loan_amount": payload.requested_loan_amount,
        "loan_duration_months": payload.loan_duration_months,
        # Tenure the customer entered. The interest rate is bank-defined and is
        # stored (frozen) via compute_emi_fields below, not entered here.
        "loan_tenure": payload.loan_tenure,
        "tenure_unit": payload.tenure_unit.value,
        "loan_purpose": payload.loan_purpose.strip(),
        "dependents": payload.dependents,
        "savings_buffer": payload.savings_buffer.value,
        "repayment_history": payload.repayment_history.value,
        "pan_number": getattr(payload, "pan_number", None),
        "collateral_type": getattr(payload, "collateral_type", None),
        "collateral_value": getattr(payload, "collateral_value", None),
        "collateral_description": getattr(payload, "collateral_description", None),
        "status": ApplicationStatus.DRAFT.value,
        "created_at": now,
        "updated_at": now,
    }
    # Auto-calculate EMI + affordability from the bank rate before saving.
    document.update(
        compute_emi_fields(
            requested_loan_amount=payload.requested_loan_amount,
            interest_rate_used=interest_rate_used,
            loan_duration_months=payload.loan_duration_months,
            existing_monthly_debt=payload.existing_monthly_debt,
            monthly_income=payload.monthly_income,
        )
    )
    return document


def create_application_draft_document(
    *,
    applicant_id: str,
    loan_type: LoanType,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "applicant_id": applicant_id,
        "loan_type": loan_type.value,
        "status": ApplicationStatus.DRAFT.value,
        "created_at": now,
        "updated_at": now,
    }


def application_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    document.setdefault("loan_type", LoanType.PERSONAL.value)
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document
