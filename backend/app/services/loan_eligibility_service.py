"""Loan eligibility rules: salary-based caps and collateral requirements.

Rules (all configurable defaults):
  * Instant loan is capped at 50% of monthly salary, has no minimum, and needs
    no collateral.
  * Every other loan type has a maximum amount = income multiple x monthly salary,
    a minimum amount of Rs 200,000, and ALWAYS requires collateral to be pledged.
"""

from typing import Any

from app.models.application import LoanType

# Maximum loan = multiple x monthly income, per loan type.
# Instant is 0.5 (50% of one month's salary); longer-term secured products allow
# a larger multiple.
INCOME_MULTIPLES: dict[str, float] = {
    LoanType.INSTANT.value: 0.5,
    LoanType.PERSONAL.value: 12.0,
    LoanType.EDUCATION.value: 24.0,
    LoanType.LOAN_AGAINST_SHARES.value: 24.0,
    LoanType.AUTO.value: 30.0,
    LoanType.VEHICLE.value: 30.0,
    LoanType.BUSINESS.value: 24.0,
    LoanType.AGRICULTURE.value: 24.0,
    LoanType.HOME.value: 60.0,
    LoanType.OTHER.value: 12.0,
}

# Kept for backwards compatibility / display: the figure the minimum is tied to.
COLLATERAL_THRESHOLD = 200000.0
# Every non-instant loan must be at least this amount.
MINIMUM_LOAN_AMOUNT = 200000.0


def income_multiple(loan_type: str) -> float:
    return INCOME_MULTIPLES.get(loan_type, INCOME_MULTIPLES[LoanType.OTHER.value])


def max_loan_amount(loan_type: str, monthly_income: float) -> float:
    """Maximum amount the applicant qualifies for, from their monthly income."""
    if monthly_income is None or monthly_income <= 0:
        return 0.0
    return round(income_multiple(loan_type) * float(monthly_income), 2)


def minimum_loan_amount(loan_type: str) -> float:
    """Instant loans have no floor; every other loan starts at Rs 200,000."""
    if loan_type == LoanType.INSTANT.value:
        return 0.0
    return MINIMUM_LOAN_AMOUNT


def requires_collateral(loan_type: str, loan_amount: float) -> bool:
    """Collateral is mandatory for every loan except instant."""
    return loan_type != LoanType.INSTANT.value


def check_eligibility(
    loan_type: str,
    loan_amount: float,
    monthly_income: float,
) -> dict[str, Any]:
    """Return an eligibility breakdown for a requested loan.

    {loan_type, monthly_income, requested_amount, max_amount, within_cap,
     min_amount, meets_minimum, requires_collateral, collateral_threshold,
     instant_cap}
    """
    cap = max_loan_amount(loan_type, monthly_income)
    requested = float(loan_amount or 0)
    is_instant = loan_type == LoanType.INSTANT.value
    minimum = minimum_loan_amount(loan_type)
    return {
        "loan_type": loan_type,
        "monthly_income": float(monthly_income or 0),
        "requested_amount": requested,
        "max_amount": cap,
        "within_cap": requested <= cap if cap > 0 else False,
        "min_amount": minimum,
        "meets_minimum": requested >= minimum if requested > 0 else False,
        "requires_collateral": requires_collateral(loan_type, requested),
        "collateral_threshold": COLLATERAL_THRESHOLD,
        # 50% of monthly salary, shown for instant loans.
        "instant_cap": round(0.5 * float(monthly_income or 0), 2) if is_instant else None,
    }
