"""EMI (Equated Monthly Installment) calculation utilities.

This module is a pure, dependency-free calculation service. It intentionally
holds no database or FastAPI logic so it can be reused from:
  * the ``/emi/calculate`` route (ad-hoc calculator),
  * the loan application service (auto-calculate + persist on save),
  * the credit risk service (feed EMI into the debt-to-income ratio),
  * the amortization schedule endpoint.

Standard EMI formula:

    EMI = P * R * (1 + R)^N / ((1 + R)^N - 1)

Where:
    P = Loan amount (principal)
    R = Monthly interest rate = Annual rate / 12 / 100
    N = Number of monthly installments
"""

from enum import StrEnum
from typing import Any


class TenureUnit(StrEnum):
    """Unit the customer used to express the loan tenure."""

    MONTHS = "months"
    YEARS = "years"


class EMIValidationError(ValueError):
    """Raised when EMI inputs are invalid (non-positive amount/rate/tenure)."""


# Affordability recommendation bands, based on the debt-to-income (DTI) ratio.
AFFORDABLE = "Affordable"
MODERATE = "Moderate"
HIGH_RISK = "High Risk"


def normalize_tenure_to_months(tenure: int, tenure_unit: str | TenureUnit) -> int:
    """Convert a tenure expressed in months or years into a month count (N)."""
    unit = TenureUnit(tenure_unit)
    months = int(tenure) * (12 if unit is TenureUnit.YEARS else 1)
    return months


def calculate_emi(
    loan_amount: float,
    annual_interest_rate: float,
    tenure: int,
    tenure_unit: str | TenureUnit = TenureUnit.MONTHS,
) -> dict[str, float]:
    """Calculate the monthly EMI, total interest and total repayment.

    Returns a dict with rounded (2 dp) values:
        {"monthly_emi": ..., "total_interest": ..., "total_payment": ...}

    Notes:
        * ``tenure`` may be given in months or years via ``tenure_unit``.
        * A zero annual interest rate is supported (interest-free loan): the
          EMI degrades to a simple ``P / N`` so we never divide by zero.
    """
    if loan_amount <= 0:
        raise EMIValidationError("Loan amount must be greater than 0.")
    if annual_interest_rate < 0:
        raise EMIValidationError("Annual interest rate must not be negative.")
    if tenure <= 0:
        raise EMIValidationError("Tenure must be greater than 0.")

    months = normalize_tenure_to_months(tenure, tenure_unit)
    if months <= 0:
        raise EMIValidationError("Tenure must resolve to at least 1 month.")

    monthly_rate = annual_interest_rate / 12 / 100

    if monthly_rate == 0:
        # Interest-free loan: principal is split evenly across the tenure.
        monthly_emi = loan_amount / months
    else:
        growth = (1 + monthly_rate) ** months
        monthly_emi = loan_amount * monthly_rate * growth / (growth - 1)

    # Round the EMI first, then derive totals from the rounded EMI so that the
    # figures the customer sees always reconcile (EMI * N == total_payment).
    monthly_emi = round(monthly_emi, 2)
    total_payment = round(monthly_emi * months, 2)
    total_interest = round(total_payment - loan_amount, 2)

    return {
        "monthly_emi": monthly_emi,
        "total_interest": total_interest,
        "total_payment": total_payment,
    }


def build_amortization_schedule(
    loan_amount: float,
    annual_interest_rate: float,
    tenure: int,
    tenure_unit: str | TenureUnit = TenureUnit.MONTHS,
) -> list[dict[str, Any]]:
    """Return the month-by-month amortization schedule.

    Each entry contains:
        month, emi, principal_paid, interest_paid, remaining_balance
    The final month's principal absorbs any rounding drift so the remaining
    balance lands exactly at 0.00.
    """
    months = normalize_tenure_to_months(tenure, tenure_unit)
    emi_result = calculate_emi(loan_amount, annual_interest_rate, tenure, tenure_unit)
    monthly_emi = emi_result["monthly_emi"]
    monthly_rate = annual_interest_rate / 12 / 100

    schedule: list[dict[str, Any]] = []
    remaining_balance = float(loan_amount)

    for month in range(1, months + 1):
        interest_paid = round(remaining_balance * monthly_rate, 2)
        principal_paid = round(monthly_emi - interest_paid, 2)

        # On the last installment, clear whatever principal is left so rounding
        # errors do not leave a few paisa outstanding.
        if month == months:
            principal_paid = round(remaining_balance, 2)
            installment = round(principal_paid + interest_paid, 2)
        else:
            installment = monthly_emi

        remaining_balance = round(remaining_balance - principal_paid, 2)
        if remaining_balance < 0:
            remaining_balance = 0.0

        schedule.append(
            {
                "month": month,
                "emi": installment,
                "principal_paid": principal_paid,
                "interest_paid": interest_paid,
                "remaining_balance": remaining_balance,
            }
        )

    return schedule


def classify_affordability(dti_ratio: float) -> str:
    """Classify affordability from a debt-to-income ratio (percentage).

        DTI <= 35%        -> Affordable
        35% < DTI <= 50%  -> Moderate
        DTI > 50%         -> High Risk
    """
    if dti_ratio <= 35:
        return AFFORDABLE
    if dti_ratio <= 50:
        return MODERATE
    return HIGH_RISK


def compute_affordability(
    monthly_emi: float,
    existing_monthly_debt: float,
    monthly_income: float,
) -> dict[str, Any]:
    """Compute the EMI-inclusive DTI ratio and the affordability recommendation.

        DTI = (existing_monthly_debt + monthly_emi) / monthly_income * 100

    Returns ``{"dti_ratio": ..., "affordability": ...}``. If income is missing
    or non-positive we cannot compute a ratio, so both values are returned as
    ``None`` rather than raising.
    """
    if not monthly_income or monthly_income <= 0:
        return {"dti_ratio": None, "affordability": None}

    dti_ratio = round(
        (existing_monthly_debt + monthly_emi) / monthly_income * 100,
        2,
    )
    return {
        "dti_ratio": dti_ratio,
        "affordability": classify_affordability(dti_ratio),
    }
