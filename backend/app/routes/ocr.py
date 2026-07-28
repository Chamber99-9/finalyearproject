from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_customer
from app.config import get_settings
from app.database import get_database
from app.models.user import UserRole
from app.schemas.ocr import OCRResultResponse, OCRVerifyRequest
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.application_service import get_owned_application
from app.services.document_service import get_document_by_id
from app.services.notification_service import (
    NotificationStorageError,
    create_notifications_for_role,
)
from app.services.ocr_service import (
    EmptyOCRTextError,
    OCRFileNotFoundError,
    OCRNotConfiguredError,
    OCRProcessingError,
    OCRResultStorageError,
    OCRResultNotFoundError,
    OCRUnreadableFileError,
    UnsupportedOCRFileError,
    extract_and_save_ocr_result,
    get_ocr_result_by_id,
    serialize_ocr_result,
    verify_ocr_result,
)
from app.utilities.rate_limit import RateLimitExceededError, enforce_rate_limit

router = APIRouter(prefix="/ocr", tags=["ocr"])
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


@router.post("/extract/{document_id}", response_model=OCRResultResponse)
async def extract_document_ocr(
    document_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    customer_id = get_authenticated_user_id(current_user)
    enforce_expensive_rate_limit(customer_id, "ocr_extract")
    document = await get_document_by_id(database, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    application = await get_owned_application(
        database,
        str(document["application_id"]),
        customer_id,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    try:
        ocr_result = await extract_and_save_ocr_result(
            database=database,
            document=document,
        )
    except UnsupportedOCRFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported OCR file type. Upload JPEG, PNG, or WebP images for OCR.",
        ) from error
    except OCRFileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file was not found on disk.",
        ) from error
    except OCRUnreadableFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is unreadable.",
        ) from error
    except OCRNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tesseract OCR is not installed or is not available in PATH.",
        ) from error
    except EmptyOCRTextError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text was found in the document.",
        ) from error
    except OCRProcessingError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR processing failed.",
        ) from error
    except OCRResultStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save OCR result.",
        ) from error

    return serialize_ocr_result(ocr_result)


async def get_owned_ocr_result(
    *,
    database: AsyncIOMotorDatabase,
    ocr_result_id: str,
    customer_id: str,
) -> dict:
    ocr_result = await get_ocr_result_by_id(database, ocr_result_id)
    if ocr_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR result not found.",
        )

    application = await get_owned_application(
        database,
        str(ocr_result["application_id"]),
        customer_id,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR result not found.",
        )

    return ocr_result


@router.get("/results/{ocr_result_id}", response_model=OCRResultResponse)
async def read_ocr_result(
    ocr_result_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    customer_id = get_authenticated_user_id(current_user)
    ocr_result = await get_owned_ocr_result(
        database=database,
        ocr_result_id=ocr_result_id,
        customer_id=customer_id,
    )
    return serialize_ocr_result(ocr_result)


@router.put("/verify/{ocr_result_id}", response_model=OCRResultResponse)
async def verify_document_ocr(
    ocr_result_id: str,
    payload: OCRVerifyRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    customer_id = get_authenticated_user_id(current_user)
    await get_owned_ocr_result(
        database=database,
        ocr_result_id=ocr_result_id,
        customer_id=customer_id,
    )

    try:
        ocr_result = await verify_ocr_result(
            database=database,
            ocr_result_id=ocr_result_id,
            corrected_data=payload.corrected_data,
        )
    except OCRResultNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR result not found.",
        ) from error

    public_ocr_result = serialize_ocr_result(ocr_result)
    try:
        await create_audit_log(
            database=database,
            user_id=customer_id,
            action="ocr_verified",
            entity_type="ocr_result",
            entity_id=public_ocr_result["id"],
            details={
                "application_id": public_ocr_result["application_id"],
                "document_id": public_ocr_result["document_id"],
                "verified_by_user": public_ocr_result["verified_by_user"],
            },
        )
        await create_notifications_for_role(
            database=database,
            role=UserRole.OFFICER,
            title="OCR data verified",
            message=(
                "A customer verified OCR data for application "
                f"{public_ocr_result['application_id']}."
            ),
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR verified, but audit log could not be created.",
        ) from error
    except NotificationStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR verified, but notification could not be created.",
        ) from error

    return serialize_ocr_result(ocr_result)
