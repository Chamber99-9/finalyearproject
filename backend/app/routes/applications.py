from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_customer
from app.config import get_settings
from app.database import get_database
from app.models.document import DocumentType
from app.models.user import UserRole
from app.schemas.application import (
    ApplicationCreateRequest,
    CounterOfferResponseRequest,
    ApplicationDraftCreateRequest,
    ApplicationResponse,
    ApplicationUpdateRequest,
)
from app.schemas.document import DocumentResponse
from app.schemas.ocr import OCRResultResponse
from app.services.application_service import (
    CollateralDocumentsMissingError,
    CollateralRequiredError,
    IncompleteApplicationError,
    LoanAmountExceedsCapError,
    ApplicationNotFoundError,
    ApplicationStatusError,
    create_draft_application,
    create_empty_draft_application,
    get_owned_application,
    list_customer_applications,
    serialize_application,
    submit_owned_application,
    respond_to_counter_offer,
    update_owned_application,
)
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.document_request_service import (
    get_latest_open_document_request,
    serialize_document_request,
)
from app.services.document_service import (
    EmptyUploadError,
    FileTooLargeError,
    FileStorageError,
    MetadataStorageError,
    UnsupportedContentTypeError,
    list_documents_for_application,
    save_application_document,
    serialize_document,
)
from app.services.notification_service import (
    NotificationStorageError,
    create_notification,
    create_notifications_for_role,
)
from app.services.ocr_service import (
    extract_and_save_ocr_result,
    get_latest_ocr_result_for_document,
    serialize_ocr_result,
)
from app.utilities.rate_limit import RateLimitExceededError, enforce_rate_limit

router = APIRouter(prefix="/applications", tags=["applications"])
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


def require_verified_kyc(current_user: dict) -> None:
    """Block loan requests until the customer's KYC is verified by an officer."""
    if current_user.get("kyc_status") != "verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete KYC verification before requesting a loan.",
        )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    payload: ApplicationCreateRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    require_verified_kyc(current_user)
    applicant_id = get_authenticated_user_id(current_user)
    application = await create_draft_application(database, applicant_id, payload)
    public_application = serialize_application(application)
    try:
        await create_audit_log(
            database=database,
            user_id=applicant_id,
            action="loan_application_created",
            entity_type="loan_application",
            entity_id=public_application["id"],
            details={
                "applicant_id": applicant_id,
                "status": public_application["status"],
                "loan_type": public_application.get("loan_type"),
            },
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application created, but audit log could not be created.",
        ) from error

    return public_application


@router.post(
    "/draft",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application_draft(
    payload: ApplicationDraftCreateRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    require_verified_kyc(current_user)
    applicant_id = get_authenticated_user_id(current_user)
    application = await create_empty_draft_application(database, applicant_id, payload)
    return serialize_application(application)


@router.get("/my", response_model=list[ApplicationResponse])
async def read_my_applications(
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    applicant_id = get_authenticated_user_id(current_user)
    applications = await list_customer_applications(database, applicant_id)
    return [serialize_application(application) for application in applications]


@router.get("/{application_id}", response_model=ApplicationResponse)
async def read_application(
    application_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    return serialize_application(application)


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    payload: ApplicationUpdateRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    try:
        application = await update_owned_application(
            database,
            application_id,
            applicant_id,
            payload,
        )
    except ApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except ApplicationStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft applications can be updated.",
        ) from error

    return serialize_application(application)


@router.post("/{application_id}/submit", response_model=ApplicationResponse)
async def submit_application(
    application_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    require_verified_kyc(current_user)
    applicant_id = get_authenticated_user_id(current_user)
    try:
        application = await submit_owned_application(database, application_id, applicant_id)
    except ApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except ApplicationStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft applications can be submitted.",
        ) from error
    except IncompleteApplicationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete all required application fields before submitting.",
        ) from error
    except LoanAmountExceedsCapError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Requested amount exceeds your eligibility cap of "
                f"{error.max_amount:,.0f} based on your monthly income."
            ),
        ) from error
    except CollateralRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Loans above 200,000 (except instant loans) require collateral. "
                "Add collateral details before submitting."
            ),
        ) from error
    except CollateralDocumentsMissingError as error:
        readable = {
            "bank_statement": "account statement",
            "property_papers": "property papers",
        }
        needed = ", ".join(readable.get(item, item) for item in error.missing)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Collateral loans require these documents: {needed}. "
                "Upload them before submitting."
            ),
        ) from error

    try:
        await create_audit_log(
            database=database,
            user_id=applicant_id,
            action="loan_application_submitted",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "applicant_id": applicant_id,
                "status": application.get("status"),
            },
        )
        await create_notification(
            database=database,
            user_id=applicant_id,
            title="Application submitted",
            message="Your loan application has been submitted for officer review.",
        )
        await create_notifications_for_role(
            database=database,
            role=UserRole.OFFICER,
            title="New application submitted",
            message=f"{application.get('full_name', 'A customer')} submitted a loan application for review.",
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application submitted, but audit log could not be created.",
        ) from error
    except NotificationStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application submitted, but notification could not be created.",
        ) from error

    return serialize_application(application)


@router.get("/{application_id}/documents", response_model=list[DocumentResponse])
async def read_application_documents(
    application_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    applicant_id = get_authenticated_user_id(current_user)
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    documents = await list_documents_for_application(database, application_id)
    return [serialize_document(document) for document in documents]


@router.get("/{application_id}/ocr-results", response_model=list[OCRResultResponse])
async def read_application_ocr_results(
    application_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    applicant_id = get_authenticated_user_id(current_user)
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    documents = await list_documents_for_application(database, application_id)
    ocr_results: list[dict] = []
    for document in documents:
        document_id = str(document.get("_id") or document.get("id") or "")
        if not document_id:
            continue

        ocr_result = await get_latest_ocr_result_for_document(database, document_id)
        if ocr_result is not None:
            ocr_results.append(serialize_ocr_result(ocr_result))

    return ocr_results


@router.get("/{application_id}/document-request")
async def read_application_document_request(
    application_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    document_request = await get_latest_open_document_request(database, application_id)
    if document_request is None:
        return {"document_request": None}

    return {"document_request": serialize_document_request(document_request)}


@router.post(
    "/{application_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_application_document(
    application_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    document_type: Annotated[DocumentType, Form(...)],
    file: Annotated[UploadFile, File(...)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    enforce_expensive_rate_limit(applicant_id, "document_upload")
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    if application.get("status") not in {
        "draft",
        "document_requested",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Documents can only be uploaded while the application is a draft "
                "or when an officer has requested additional documents."
            ),
        )
    if application.get("status") == "document_requested":
        document_request = await get_latest_open_document_request(database, application_id)
        requested_document_types = set(document_request.get("document_types", [])) if document_request else set()
        if document_type.value not in requested_document_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only documents requested by the loan officer can be uploaded now.",
            )

    try:
        document = await save_application_document(
            database=database,
            application_id=application_id,
            user_id=applicant_id,
            document_type=document_type,
            file=file,
            upload_dir=settings.upload_dir,
            max_upload_bytes=settings.max_upload_bytes,
        )
    except UnsupportedContentTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload PDF, JPEG, PNG, or WebP files only.",
        ) from error
    except EmptyUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file cannot be empty.",
        ) from error
    except FileTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file is too large.",
        ) from error
    except FileStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save uploaded file.",
        ) from error
    except MetadataStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save document metadata.",
        ) from error

    # Customers no longer run OCR themselves — document verification is manual.
    # We still auto-extract text server-side (best-effort) purely so the officer
    # review screen can show a "detected document type" hint. Any failure
    # (PDFs, unreadable images, OCR not installed) is silently ignored.
    try:
        await extract_and_save_ocr_result(database=database, document=document)
    except Exception:  # noqa: BLE001 - detection hint is best-effort only
        pass

    public_document = serialize_document(document)
    try:
        await create_audit_log(
            database=database,
            user_id=applicant_id,
            action="document_uploaded",
            entity_type="application_document",
            entity_id=public_document["id"],
            details={
                "application_id": application_id,
                "document_type": public_document["document_type"],
                "filename": public_document["filename"],
                "file_hash": public_document["file_hash"],
            },
        )
        await create_notifications_for_role(
            database=database,
            role=UserRole.OFFICER,
            title="Document uploaded",
            message=(
                f"{application.get('full_name', 'A customer')} uploaded "
                f"{public_document['document_type']} for application {application_id}."
            ),
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document uploaded, but audit log could not be created.",
        ) from error

    return public_document


@router.post("/{application_id}/counter-offer/respond", response_model=ApplicationResponse)
async def respond_application_counter_offer(
    application_id: str,
    payload: CounterOfferResponseRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    try:
        application = await respond_to_counter_offer(
            database,
            application_id,
            applicant_id,
            payload.accepted,
        )
    except ApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except ApplicationStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending counter offer is available for this application.",
        ) from error

    action = "counter_offer_accepted" if payload.accepted else "counter_offer_declined"
    try:
        await create_audit_log(
            database=database,
            user_id=applicant_id,
            action=action,
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "offered_loan_amount": application.get("offered_loan_amount"),
                "new_status": application.get("status"),
            },
        )
        await create_notifications_for_role(
            database=database,
            role=UserRole.OFFICER,
            title="Counter offer response",
            message=(
                f"{application.get('full_name', 'A customer')} "
                f"{'accepted' if payload.accepted else 'declined'} the loan amount offer."
            ),
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Counter offer response saved, but audit log could not be created.",
        ) from error
    except NotificationStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Counter offer response saved, but notification could not be created.",
        ) from error

    return serialize_application(application)
