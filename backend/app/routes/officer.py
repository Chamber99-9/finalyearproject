from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_officer
from app.database import get_database
from app.schemas.admin import BlacklistRequest
from app.schemas.application import ApplicationResponse
from app.schemas.payments import PaymentConfirmRequest, PaymentRejectRequest, PaymentResponse
from app.schemas.user import UserResponse
from app.services.audit_service import create_audit_log
from app.services.notification_service import create_notification
from app.services.payment_service import (
    PaymentNotFoundError,
    confirm_payment,
    list_pending_confirmations,
    reject_payment,
    serialize_payment,
)
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


@router.get("/payments/pending", response_model=list[PaymentResponse])
async def read_pending_payments(
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    """QR payments customers marked paid, awaiting confirmation of receipt."""
    payments = await list_pending_confirmations(database)
    return [serialize_payment(payment) for payment in payments]


@router.post("/payments/{payment_id}/confirm", response_model=PaymentResponse)
async def confirm_payment_route(
    payment_id: str,
    payload: PaymentConfirmRequest,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Officer has checked the account number and amount deposited against the
    bank statement — confirm the receipt and cut the EMI by what was verified."""
    officer_id = get_authenticated_user_id(current_user)
    try:
        payment = await confirm_payment(
            database,
            payment_id,
            officer_id=officer_id,
            verified_amount=payload.verified_amount,
            notes=payload.notes,
        )
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        ) from error

    await create_audit_log(
        database=database,
        user_id=officer_id,
        action="payment_confirmed",
        entity_type="payment",
        entity_id=payment_id,
        details={
            "actor_role": "officer",
            "verified_amount": payment.get("verified_amount"),
            "is_partial": payment.get("is_partial"),
        },
    )
    if payment.get("status") == "success":
        amount_text = f"NPR {payment.get('amount_paid')}" if payment.get("amount_paid") is not None else "Your payment"
        message = f"{amount_text} was verified and applied to your loan."
        if payment.get("is_partial"):
            message += (
                f" This was less than the full EMI, so NPR {payment.get('shortfall')} is still due "
                "to complete this installment."
            )
        await create_notification(
            database=database,
            user_id=str(payment.get("applicant_id")),
            title="Payment confirmed",
            message=message,
        )
    return serialize_payment(payment)


@router.post("/payments/{payment_id}/reject", response_model=PaymentResponse)
async def reject_payment_route(
    payment_id: str,
    payload: PaymentRejectRequest,
    current_user: Annotated[dict, Depends(require_officer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Officer could not match the receipt (wrong account / amount) — reject it."""
    officer_id = get_authenticated_user_id(current_user)
    try:
        payment = await reject_payment(
            database, payment_id, officer_id=officer_id, reason=payload.reason
        )
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        ) from error

    await create_audit_log(
        database=database,
        user_id=officer_id,
        action="payment_rejected",
        entity_type="payment",
        entity_id=payment_id,
        details={"actor_role": "officer", "reason": payload.reason},
    )
    await create_notification(
        database=database,
        user_id=str(payment.get("applicant_id")),
        title="Payment could not be verified",
        message=(
            f"Your receipt could not be matched to a deposit: {payload.reason} "
            "Please check the details and resubmit."
        ),
    )
    return serialize_payment(payment)


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
