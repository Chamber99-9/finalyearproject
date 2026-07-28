"""EMI calculator routes.

Endpoints:
    POST /emi/calculate              -> ad-hoc EMI calculation (any signed-in user)
    POST /emi/preview                -> customer preview using the bank-defined rate
    GET  /emi/schedule/{application_id} -> amortization schedule for a stored application
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, get_current_user
from app.database import get_database
from app.models.application import LoanType
from app.models.user import UserRole
from app.schemas.emi import (
    AmortizationScheduleResponse,
    EMICalculateRequest,
    EMIPreviewRequest,
    EMIPreviewResponse,
    EMIResponse,
)
from app.services.application_service import get_application_by_id
from app.services.emi_service import (
    EMIValidationError,
    TenureUnit,
    build_amortization_schedule,
    calculate_emi,
    normalize_tenure_to_months,
)
from app.services.loan_settings_service import get_loan_interest_rate

router = APIRouter(prefix="/emi", tags=["emi"])


@router.post("/preview", response_model=EMIPreviewResponse)
async def preview_emi_route(
    payload: EMIPreviewRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Preview the EMI for a Personal Loan using the bank-defined rate.

    The customer supplies only amount + tenure; the interest rate is read from
    the bank settings and returned so the form can display it read-only.
    """
    interest_rate_used = await get_loan_interest_rate(database, LoanType.PERSONAL.value)
    try:
        emi = calculate_emi(
            loan_amount=payload.loan_amount,
            annual_interest_rate=interest_rate_used,
            tenure=payload.tenure,
            tenure_unit=payload.tenure_unit,
        )
    except EMIValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return {"interest_rate_used": interest_rate_used, **emi}


@router.post("/calculate", response_model=EMIResponse)
async def calculate_emi_route(
    payload: EMICalculateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Return monthly EMI, total interest and total repayment for the inputs.

    Requires authentication so customers can preview an EMI while filling in a
    loan application, and officers can model scenarios during review.
    """
    try:
        return calculate_emi(
            loan_amount=payload.loan_amount,
            annual_interest_rate=payload.annual_interest_rate,
            tenure=payload.tenure,
            tenure_unit=payload.tenure_unit,
        )
    except EMIValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/schedule/{application_id}", response_model=AmortizationScheduleResponse)
async def get_amortization_schedule(
    application_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Return the full month-by-month amortization schedule for an application.

    Access control: the owning customer, or any officer/admin, may view it.
    """
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # A customer may only view their own application; officers/admins may view any.
    role = current_user.get("role")
    if role == UserRole.CUSTOMER.value:
        if str(application.get("applicant_id")) != get_authenticated_user_id(current_user):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )
    elif role not in {UserRole.OFFICER.value, UserRole.ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this schedule.",
        )

    loan_amount = application.get("requested_loan_amount")
    # Use the exact rate frozen on the application (falls back to legacy field).
    annual_interest_rate = application.get("interest_rate_used")
    if annual_interest_rate is None:
        annual_interest_rate = application.get("annual_interest_rate")
    # loan_duration_months is the canonical installment count (N) on the document.
    tenure_months = application.get("loan_duration_months")

    if loan_amount is None or annual_interest_rate is None or tenure_months is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Application is missing loan amount, interest rate, or tenure. "
                "Complete the application before requesting a schedule."
            ),
        )

    try:
        emi_result = calculate_emi(
            loan_amount=float(loan_amount),
            annual_interest_rate=float(annual_interest_rate),
            tenure=int(tenure_months),
            tenure_unit=TenureUnit.MONTHS,
        )
        schedule = build_amortization_schedule(
            loan_amount=float(loan_amount),
            annual_interest_rate=float(annual_interest_rate),
            tenure=int(tenure_months),
            tenure_unit=TenureUnit.MONTHS,
        )
    except EMIValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return {
        "application_id": application_id,
        "loan_amount": float(loan_amount),
        "annual_interest_rate": float(annual_interest_rate),
        "tenure_months": normalize_tenure_to_months(int(tenure_months), TenureUnit.MONTHS),
        "monthly_emi": emi_result["monthly_emi"],
        "total_interest": emi_result["total_interest"],
        "total_payment": emi_result["total_payment"],
        "schedule": schedule,
    }
