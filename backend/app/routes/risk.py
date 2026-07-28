from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_officer_or_admin
from app.config import get_settings
from app.database import get_database
from app.schemas.risk import CreditRiskResponse
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.application_service import get_application_by_id
from app.services.risk_service import (
    RiskScoreStorageError,
    RiskValidationError,
    calculate_and_save_credit_risk,
    serialize_risk_score,
)
from app.utilities.rate_limit import RateLimitExceededError, enforce_rate_limit

router = APIRouter(prefix="/risk", tags=["risk"])
settings = get_settings()


def enforce_expensive_rate_limit(user_id: str, action: str) -> None:
    try:
        enforce_rate_limit(
            key=f"expensive:{action}:user:{user_id}",
            limit=settings.expensive_rate_limit_count,
            window_seconds=settings.expensive_rate_limit_window_seconds,
        )
    except RateLimitExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        ) from error


@router.post("/calculate/{application_id}", response_model=CreditRiskResponse)
async def calculate_application_risk(
    application_id: str,
    current_user: Annotated[dict, Depends(require_officer_or_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    user_id = get_authenticated_user_id(current_user)
    enforce_expensive_rate_limit(user_id, "risk_calculate")

    application = await get_application_by_id(database, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    try:
        risk_score = await calculate_and_save_credit_risk(database, application)
    except RiskValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except RiskScoreStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save credit risk score.",
        ) from error

    public_risk_score = serialize_risk_score(risk_score)
    try:
        await create_audit_log(
            database=database,
            user_id=user_id,
            action="credit_score_calculated",
            entity_type="credit_risk_score",
            entity_id=public_risk_score["id"],
            details={
                "application_id": application_id,
                "raw_score": public_risk_score["raw_score"],
                "normalized_score": public_risk_score["normalized_score"],
                "risk_level": public_risk_score["risk_level"],
                "score_type": public_risk_score["score_type"],
                "repayment_history_used": public_risk_score["repayment_history_used"],
                "scoring_model_version": public_risk_score["scoring_model_version"],
            },
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Credit score calculated, but audit log could not be created.",
        ) from error

    return public_risk_score
