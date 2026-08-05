from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_officer
from app.database import get_database
from app.schemas.admin import BlacklistRequest
from app.schemas.application import ApplicationResponse
from app.schemas.user import UserResponse
from app.services.audit_service import create_audit_log
from app.services.notification_service import create_notification
from app.services.user_service import serialize_user, set_user_blacklist
from app.schemas.officer import (
    AdditionalDocumentRequestCreate,
    AdditionalDocumentRequestResponse,
    ApplicationStatusUpdateRequest,
    CounterOfferCreate,
    OfficerApplicationDetailResponse,
    OfficerVerificationUpdate,
)
from app.services.document_request_service import serialize_document_request
from app.services.document_service import get_document_by_id
from app.services.officer_service import (
    OfficerApplicationNotFoundError,
    OfficerWorkflowStorageError,
    CounterOfferValidationError,
    create_counter_offer,
    get_officer_application_detail,
    list_review_applications,
    request_additional_documents,
    update_officer_application_status,
    update_verification_checklist,
)

router = APIRouter(prefix="/officer", tags=["officer"])


@router.put("/users/{user_id}/blacklist", response_model=UserResponse)
async def officer_blacklist_user(
    user_id: str,
    payload: BlacklistRequest,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Blacklist (or restore) a customer. A blacklisted customer cannot log in."""
    updated = await set_user_blacklist(database, user_id, payload.blacklisted)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    action = "user_blacklisted" if payload.blacklisted else "user_unblacklisted"
    await create_audit_log(
        database=database,
        user_id=get_authenticated_user_id(current_user),
        action=action,
        entity_type="user",
        entity_id=user_id,
        details={"actor_role": "officer", "blacklisted": payload.blacklisted},
    )
    await create_notification(
        database=database,
        user_id=user_id,
        title="Account blacklisted" if payload.blacklisted else "Account restored",
        message=(
            "Your account has been blacklisted. Please contact the bank."
            if payload.blacklisted
            else "Your account has been restored. You can log in again."
        ),
    )
    return serialize_user(updated)


@router.get("/applications", response_model=list[ApplicationResponse])
async def read_officer_applications(
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    return await list_review_applications(database)


@router.get(
    "/applications/{application_id}",
    response_model=OfficerApplicationDetailResponse,
)
async def read_officer_application_detail(
    application_id: str,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    try:
        return await get_officer_application_detail(database, application_id)
    except OfficerApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error


@router.get("/documents/{document_id}/download")
async def download_officer_application_document(
    document_id: str,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> FileResponse:
    document = await get_document_by_id(database, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    file_path = Path(str(document.get("file_path") or ""))
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        )

    return FileResponse(
        path=file_path,
        media_type=str(document.get("content_type") or "application/octet-stream"),
        filename=str(document.get("filename") or file_path.name),
    )


@router.put(
    "/applications/{application_id}/status",
    response_model=ApplicationResponse,
)
async def update_officer_application_status_route(
    application_id: str,
    payload: ApplicationStatusUpdateRequest,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    try:
        return await update_officer_application_status(
            database=database,
            application_id=application_id,
            payload=payload,
            current_user=current_user,
        )
    except OfficerApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except OfficerWorkflowStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update application status.",
        ) from error


@router.post(
    "/applications/{application_id}/request-document",
    response_model=AdditionalDocumentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_officer_application_document(
    application_id: str,
    payload: AdditionalDocumentRequestCreate,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    try:
        document_request = await request_additional_documents(
            database=database,
            application_id=application_id,
            payload=payload,
            current_user=current_user,
        )
    except OfficerApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except OfficerWorkflowStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not request additional documents.",
        ) from error

    return serialize_document_request(document_request)


@router.put(
    "/applications/{application_id}/verification",
    response_model=ApplicationResponse,
)
async def update_application_verification(
    application_id: str,
    payload: OfficerVerificationUpdate,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Record officer sign-off on PAN / stamp / signature / collateral checks."""
    try:
        return await update_verification_checklist(
            database=database,
            application_id=application_id,
            payload=payload,
            current_user=current_user,
        )
    except OfficerApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except OfficerWorkflowStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save verification checklist.",
        ) from error


@router.post(
    "/applications/{application_id}/counter-offer",
    response_model=ApplicationResponse,
)
async def send_officer_counter_offer(
    application_id: str,
    payload: CounterOfferCreate,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    try:
        return await create_counter_offer(
            database=database,
            application_id=application_id,
            payload=payload,
            current_user=current_user,
        )
    except OfficerApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except CounterOfferValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offer amount must be lower than the requested loan amount.",
        ) from error
    except OfficerWorkflowStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not send counter offer.",
        ) from error
