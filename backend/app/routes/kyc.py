"""KYC routes.

    POST /kyc/submit           -> customer submits KYC
    GET  /kyc/me               -> customer's KYC status
    GET  /kyc                  -> pending KYC queue (officer/admin)
    PUT  /kyc/{user_id}/review -> approve/reject (officer/admin)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import (
    get_authenticated_user_id,
    require_customer,
    require_officer_or_admin,
)
from app.database import get_database
from app.schemas.kyc import KycResponse, KycReviewRequest, KycSubmitRequest
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.kyc_service import (
    KycNotFoundError,
    get_kyc_for_user,
    list_pending_kyc,
    review_kyc,
    serialize_kyc,
    submit_kyc,
)

router = APIRouter(prefix="/kyc", tags=["kyc"])


@router.post("/submit", response_model=KycResponse)
async def submit_kyc_route(
    payload: KycSubmitRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    user_id = get_authenticated_user_id(current_user)
    record = await submit_kyc(database, user_id, payload)
    return serialize_kyc(record)


@router.get("/me", response_model=KycResponse | None)
async def read_my_kyc(
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict | None:
    user_id = get_authenticated_user_id(current_user)
    record = await get_kyc_for_user(database, user_id)
    return serialize_kyc(record) if record is not None else None


@router.get("", response_model=list[KycResponse])
async def read_pending_kyc(
    current_user: Annotated[dict, Depends(require_officer_or_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    records = await list_pending_kyc(database)
    return [serialize_kyc(record) for record in records]


@router.put("/{user_id}/review", response_model=KycResponse)
async def review_kyc_route(
    user_id: str,
    payload: KycReviewRequest,
    current_user: Annotated[dict, Depends(require_officer_or_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    try:
        record = await review_kyc(database, user_id, payload)
    except KycNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC record not found.",
        ) from error

    try:
        await create_audit_log(
            database=database,
            user_id=get_authenticated_user_id(current_user),
            action="kyc_reviewed",
            entity_type="kyc",
            entity_id=user_id,
            details={"status": record.get("status"), "note": payload.note},
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="KYC reviewed, but audit log could not be created.",
        ) from error

    return serialize_kyc(record)
