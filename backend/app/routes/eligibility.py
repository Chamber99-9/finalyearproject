"""Loan eligibility + mock verification routes.

    POST /loan-eligibility/check      -> salary cap + collateral requirement
    POST /verification/pan            -> PAN format + mock tax registry
    POST /verification/salary-statement -> salary-statement sanity check
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.schemas.eligibility import (
    EligibilityCheckRequest,
    EligibilityResponse,
    PanCheckRequest,
    PanCheckResponse,
    SalaryCheckRequest,
    SalaryCheckResponse,
)
from app.services.loan_eligibility_service import check_eligibility
from app.services.verification_service import verify_pan, verify_salary_statement

eligibility_router = APIRouter(prefix="/loan-eligibility", tags=["eligibility"])
verification_router = APIRouter(prefix="/verification", tags=["verification"])


@eligibility_router.post("/check", response_model=EligibilityResponse)
async def check_loan_eligibility(
    payload: EligibilityCheckRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Return the salary-based cap and collateral requirement for a request."""
    return check_eligibility(
        loan_type=payload.loan_type,
        loan_amount=payload.loan_amount,
        monthly_income=payload.monthly_income,
    )


@verification_router.post("/pan", response_model=PanCheckResponse)
async def check_pan(
    payload: PanCheckRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Validate a PAN number against the mock tax registry."""
    return verify_pan(payload.pan_number)


@verification_router.post("/salary-statement", response_model=SalaryCheckResponse)
async def check_salary_statement(
    payload: SalaryCheckRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Sanity-check a salary statement's stated income against the declared income."""
    return verify_salary_statement(
        stated_monthly_income=payload.stated_monthly_income,
        declared_monthly_income=payload.declared_monthly_income,
        employer_name=payload.employer_name,
    )
