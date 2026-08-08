"""Dynamic loan interest-rate engine.

Effective annual rate = base lending rate
                        + loan-type spread
                        + tenure adjustment (longer tenure -> higher rate)

The base rate is bank-defined (loan_settings_service, admin-overridable). The
per-type spreads and tenure model live here with sensible, fully configurable
defaults. Designed so new loan products only need a new spread entry.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.application import LoanType
from app.services.emi_service import TenureUnit, normalize_tenure_to_months
from app.services.loan_settings_service import get_base_lending_rate

# Annual percentage points added on top of the base rate, per loan type.
# Unsecured / higher-risk products carry a larger spread.
LOAN_TYPE_SPREADS: dict[str, float] = {
    LoanType.INSTANT.value: 6.0,
    LoanType.PERSONAL.value: 3.0,
    LoanType.LOAN_AGAINST_SHARES.value: 2.5,
    LoanType.BUSINESS.value: 2.0,
    LoanType.AUTO.value: 2.0,
    LoanType.VEHICLE.value: 2.0,
    LoanType.AGRICULTURE.value: 1.75,
    LoanType.EDUCATION.value: 1.5,
    LoanType.HOME.value: 1.0,
    LoanType.OTHER.value: 2.0,
}

# Longer tenure -> higher rate. Added per year, capped.
TENURE_ADJUSTMENT_PER_YEAR = 0.1
TENURE_ADJUSTMENT_CAP = 2.0

# Human-friendly labels and typical tenure guidance for the UI menu.
LOAN_TYPE_INFO: list[dict[str, Any]] = [
    {"loan_type": LoanType.PERSONAL.value, "label": "Personal loan", "requires_collateral_above": 200000, "max_tenure_years": 7},
    {"loan_type": LoanType.INSTANT.value, "label": "Instant loan", "requires_collateral_above": None, "max_tenure_years": 1},
    {"loan_type": LoanType.HOME.value, "label": "Home loan", "requires_collateral_above": 200000, "max_tenure_years": 25},
    {"loan_type": LoanType.AUTO.value, "label": "Auto loan", "requires_collateral_above": 200000, "max_tenure_years": 10},
    {"loan_type": LoanType.EDUCATION.value, "label": "Education loan", "requires_collateral_above": 200000, "max_tenure_years": 10},
    {"loan_type": LoanType.BUSINESS.value, "label": "Business loan", "requires_collateral_above": 200000, "max_tenure_years": 10},
]


def get_type_spread(loan_type: str) -> float:
    return LOAN_TYPE_SPREADS.get(loan_type, LOAN_TYPE_SPREADS[LoanType.OTHER.value])


def tenure_adjustment(tenure_months: int) -> float:
    """Rate bump for tenure length (per year, capped). Rounded to 2 dp."""
    years = tenure_months / 12
    return round(min(years * TENURE_ADJUSTMENT_PER_YEAR, TENURE_ADJUSTMENT_CAP), 2)


async def compute_effective_rate(
    database: AsyncIOMotorDatabase,
    loan_type: str,
    tenure_months: int,
) -> dict[str, Any]:
    """Return the rate breakdown for a loan type + tenure.

    {loan_type, base_rate, type_spread, tenure_adjustment, effective_rate}
    """
    base_rate = await get_base_lending_rate(database)
    type_spread = get_type_spread(loan_type)
    adjustment = tenure_adjustment(int(tenure_months))
    effective_rate = round(base_rate + type_spread + adjustment, 2)
    return {
        "loan_type": loan_type,
        "base_rate": round(base_rate, 2),
        "type_spread": type_spread,
        "tenure_adjustment": adjustment,
        "effective_rate": effective_rate,
    }


async def effective_rate_value(
    database: AsyncIOMotorDatabase,
    loan_type: str,
    tenure: int,
    tenure_unit: str | TenureUnit = TenureUnit.MONTHS,
) -> float:
    """Convenience: just the effective rate for a tenure given in months/years."""
    tenure_months = normalize_tenure_to_months(tenure, tenure_unit)
    breakdown = await compute_effective_rate(database, loan_type, tenure_months)
    return breakdown["effective_rate"]
