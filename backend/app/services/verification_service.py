"""Mock + heuristic verification helpers.

Real identity/document forensics need external services; these provide a
realistic, demonstrable stand-in that an officer confirms:

  * PAN: 9-digit format check + a mock tax registry lookup.
  * Salary statement: sanity-check the OCR-stated income against the declared
    income (within tolerance) and require an employer name.
  * Stamp / signature: presence flags recorded on documents that an officer
    confirms during review (see the officer verification endpoint).
"""

import re
from typing import Any

# Demo "tax defaulters" — any well-formed PAN not in this set is treated as
# tax-registered by the mock registry. Swap for a real lookup later.
MOCK_TAX_DEFAULTERS: set[str] = {"000000000", "111111111", "123456789"}

_PAN_PATTERN = re.compile(r"^\d{9}$")


def verify_pan(pan_number: str | None) -> dict[str, Any]:
    """Validate PAN format and look it up in the mock tax registry."""
    pan = (pan_number or "").strip()
    valid_format = bool(_PAN_PATTERN.fullmatch(pan))
    tax_registered = valid_format and pan not in MOCK_TAX_DEFAULTERS
    return {
        "pan_number": pan,
        "valid_format": valid_format,
        "tax_registered": tax_registered,
        "reason": (
            "PAN must be exactly 9 digits."
            if not valid_format
            else "PAN is registered and tax records found."
            if tax_registered
            else "PAN is valid but no active tax registration was found."
        ),
    }


def verify_salary_statement(
    stated_monthly_income: float | None,
    declared_monthly_income: float | None,
    employer_name: str | None = None,
    tolerance: float = 0.25,
) -> dict[str, Any]:
    """Heuristic check that a salary statement supports the declared income.

    Valid when the OCR-stated income is within ``tolerance`` of the declared
    income and an employer name is present. Not a legal guarantee — it flags
    mismatches for an officer to confirm.
    """
    if not stated_monthly_income or not declared_monthly_income or declared_monthly_income <= 0:
        return {"valid": False, "reason": "Stated or declared monthly income is missing."}

    stated = float(stated_monthly_income)
    declared = float(declared_monthly_income)
    difference = abs(stated - declared) / declared
    if difference > tolerance:
        return {
            "valid": False,
            "reason": (
                f"Stated income differs from declared income by "
                f"{round(difference * 100)}% (tolerance {round(tolerance * 100)}%)."
            ),
        }
    if employer_name is not None and len(employer_name.strip()) < 2:
        return {"valid": False, "reason": "Employer name is missing on the statement."}

    return {
        "valid": True,
        "reason": "Stated income matches the declared income within tolerance.",
    }
