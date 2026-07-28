from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_officer_or_admin
from app.config import get_settings
from app.database import get_database
from app.schemas.flags import ApplicationFlagsResponse
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.application_service import get_application_by_id
from app.services.flag_service import (
    ApplicationFlagStorageError,
    check_and_save_application_flags,
    serialize_application_flags,
)
from app.utilities.rate_limit import RateLimitExceededError, enforce_rate_limit

router = APIRouter(prefix="/flags", tags=["flags"])
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


@router.post("/check/{application_id}", response_model=ApplicationFlagsResponse)
async def check_application_flags(
    application_id: str,
    current_user: Annotated[dict, Depends(require_officer_or_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    user_id = get_authenticated_user_id(current_user)
    enforce_expensive_rate_limit(user_id, "flags_check")

    application = await get_application_by_id(database, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    try:
        flag_result = await check_and_save_application_flags(database, application)
    except ApplicationFlagStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save suspicious application flags.",
        ) from error

    public_flag_result = serialize_application_flags(flag_result)
    try:
        await create_audit_log(
            database=database,
            user_id=user_id,
            action="suspicious_flag_check_completed",
            entity_type="application_flags",
            entity_id=public_flag_result.get("id") or application_id,
            details={
                "application_id": application_id,
                "total_flags": public_flag_result["total_flags"],
                "suspicion_level": public_flag_result["suspicion_level"],
            },
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Suspicious flag check completed, but audit log could not be created.",
        ) from error

    return public_flag_result
