"""Bank loan settings routes.

    GET /loan-settings/personal-rate   -> current Personal Loan rate (any user)
    PUT /loan-settings/personal-rate   -> update the bank default (admin only)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, get_current_user, require_admin
from app.database import get_database
from app.models.application import LoanType
from app.schemas.settings import LoanInterestRateResponse, LoanInterestRateUpdateRequest
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.loan_settings_service import (
    LoanSettingsError,
    get_personal_loan_interest_rate,
    set_personal_loan_interest_rate,
)

router = APIRouter(prefix="/loan-settings", tags=["loan-settings"])


@router.get("/personal-rate", response_model=LoanInterestRateResponse)
async def read_personal_rate(
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Return the current Personal Loan interest rate.

    Available to any signed-in user so the customer application form can show
    the bank rate and preview an EMI without ever entering the rate manually.
    """
    rate = await get_personal_loan_interest_rate(database)
    return {"loan_type": LoanType.PERSONAL.value, "interest_rate": rate}


@router.put("/personal-rate", response_model=LoanInterestRateResponse)
async def update_personal_rate(
    payload: LoanInterestRateUpdateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Update the bank default Personal Loan interest rate (admin only).

    Note: existing applications keep the ``interest_rate_used`` captured at their
    application time — changing the default here never alters past applications.
    """
    try:
        rate = await set_personal_loan_interest_rate(database, payload.interest_rate)
    except LoanSettingsError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    try:
        await create_audit_log(
            database=database,
            user_id=get_authenticated_user_id(current_user),
            action="personal_loan_rate_updated",
            entity_type="app_settings",
            entity_id="loan_interest_rate:personal",
            details={"new_interest_rate": rate},
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interest rate updated, but audit log could not be created.",
        ) from error

    return {"loan_type": LoanType.PERSONAL.value, "interest_rate": rate}
