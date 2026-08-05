import re
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.application import ApplicationStatus, compute_emi_fields
from app.models.user import UserRole
from app.schemas.officer import (
    AdditionalDocumentRequestCreate,
    ApplicationStatusUpdateRequest,
    CounterOfferCreate,
    InterestRateUpdateRequest,
    OfficerVerificationUpdate,
)
from app.services.application_service import (
    get_application_by_id,
    list_officer_applications,
    serialize_application,
    update_application_status,
)
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.document_request_service import (
    DocumentRequestStorageError,
    create_document_request,
)
from app.services.document_service import list_documents_for_application, serialize_document
from app.services.flag_service import (
    get_latest_application_flags,
    serialize_application_flags,
)
from app.services.ocr_service import (
    get_latest_ocr_result_for_document,
    serialize_ocr_result,
)
from app.services.notification_service import (
    NotificationStorageError,
    create_notification,
)
from app.services.loan_account_service import create_loan_account_for_application
from app.services.user_service import get_user_by_id
from app.services.risk_service import (
    get_latest_risk_score_for_application,
    serialize_risk_score,
)


class OfficerApplicationNotFoundError(Exception):
    pass


class OfficerWorkflowStorageError(Exception):
    pass


class CounterOfferValidationError(Exception):
    pass


class ApplicationIncompleteForRateError(Exception):
    """Raised when an application lacks amount/tenure needed to recompute EMI."""


def _name_tokens(name: str | None) -> set[str]:
    """Significant (>=3 char) alphabetic tokens of a name, lowercased."""
    cleaned = re.sub(r"[^a-z ]", " ", (name or "").lower())
    return {token for token in cleaned.split() if len(token) >= 3}


def compute_name_match(
    application: dict[str, Any],
    ocr_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Flag (never block) when the person's name differs across documents.

    Compares each document's detected name against the application's full name.
    Returns status match/mismatch/insufficient plus the names involved so the
    officer can eyeball it. OCR names are noisy, so this is advisory only.
    """
    base = _name_tokens(application.get("full_name"))
    document_names: list[str] = []
    mismatched: list[str] = []
    for result in ocr_results:
        detected = (result.get("detected_fields") or {}).get("name")
        if not detected:
            continue
        document_names.append(detected)
        tokens = _name_tokens(detected)
        if base and tokens and not (base & tokens):
            mismatched.append(detected)

    if not base or not document_names:
        status = "insufficient"
        match: bool | None = None
    else:
        match = len(mismatched) == 0
        status = "match" if match else "mismatch"

    return {
        "status": status,
        "match": match,
        "application_name": application.get("full_name"),
        "document_names": document_names,
        "mismatched_names": mismatched,
    }


async def list_review_applications(
    database: AsyncIOMotorDatabase,
) -> list[dict[str, Any]]:
    applications = await list_officer_applications(database)
    return [serialize_application(application) for application in applications]


async def get_officer_application_detail(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> dict[str, Any]:
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise OfficerApplicationNotFoundError

    application_id = str(application["_id"])
    # Attach the applicant's email (from their account) for officer review.
    applicant = await get_user_by_id(database, str(application.get("applicant_id") or ""))
    if applicant is not None:
        application["applicant_email"] = applicant.get("email")

    documents = await list_documents_for_application(database, application_id)
    ocr_results: list[dict[str, Any]] = []
    for document in documents:
        document_id = str(document.get("_id") or document.get("id"))
        if not document_id:
            continue

        ocr_result = await get_latest_ocr_result_for_document(database, document_id)
        if ocr_result is not None:
            ocr_results.append(serialize_ocr_result(ocr_result))

    risk_score = await get_latest_risk_score_for_application(database, application_id)
    suspicious_flags = await get_latest_application_flags(database, application_id)

    return {
        "application": serialize_application(application),
        "documents": [serialize_document(document) for document in documents],
        "ocr_results": ocr_results,
        "name_match": compute_name_match(application, ocr_results),
        "credit_risk_score": (
            serialize_risk_score(risk_score) if risk_score is not None else None
        ),
        "suspicious_flags": (
            serialize_application_flags(suspicious_flags)
            if suspicious_flags is not None
            else None
        ),
    }


def get_actor_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("_id") or current_user.get("id"))


async def update_officer_application_status(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    payload: ApplicationStatusUpdateRequest,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise OfficerApplicationNotFoundError

    updated_application = await update_application_status(
        database,
        application_id,
        payload.status,
    )
    if updated_application is None:
        raise OfficerApplicationNotFoundError

    # On approval, open a loan account so the repayment lifecycle can begin.
    if payload.status == ApplicationStatus.APPROVED:
        await create_loan_account_for_application(database, updated_application)

    try:
        await create_audit_log(
            database=database,
            user_id=get_actor_id(current_user),
            action="officer_status_updated",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "actor_role": UserRole.OFFICER.value,
                "previous_status": str(application.get("status")),
                "new_status": payload.status.value,
                "note": payload.note,
            },
        )
        if payload.status in {ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}:
            status_label = (
                "approved"
                if payload.status == ApplicationStatus.APPROVED
                else "rejected"
            )
            await create_notification(
                database=database,
                user_id=str(application.get("applicant_id")),
                title=f"Application {status_label}",
                message=f"Your loan application has been {status_label}.",
            )
    except (AuditLogStorageError, NotificationStorageError) as error:
        raise OfficerWorkflowStorageError from error

    return serialize_application(updated_application)


async def create_counter_offer(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    payload: CounterOfferCreate,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise OfficerApplicationNotFoundError

    requested_amount = application.get("requested_loan_amount")
    if isinstance(requested_amount, (int, float)) and payload.offered_loan_amount >= requested_amount:
        raise CounterOfferValidationError

    actor_id = get_actor_id(current_user)
    previous_status = str(application.get("status"))
    updated_application = await database["loan_applications"].find_one_and_update(
        {"_id": application["_id"]},
        {
            "$set": {
                "status": ApplicationStatus.COUNTER_OFFERED.value,
                "offered_loan_amount": payload.offered_loan_amount,
                "offer_message": payload.message,
                "offer_status": "pending",
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_application is None:
        raise OfficerApplicationNotFoundError

    try:
        await create_audit_log(
            database=database,
            user_id=actor_id,
            action="counter_offer_sent",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "actor_role": UserRole.OFFICER.value,
                "previous_status": previous_status,
                "new_status": ApplicationStatus.COUNTER_OFFERED.value,
                "requested_loan_amount": requested_amount,
                "offered_loan_amount": payload.offered_loan_amount,
            },
        )
        await create_notification(
            database=database,
            user_id=str(application.get("applicant_id")),
            title="Loan amount offer received",
            message=(
                f"A loan officer offered NPR {payload.offered_loan_amount:,.0f}. "
                f"{payload.message}"
            ),
        )
    except (AuditLogStorageError, NotificationStorageError) as error:
        raise OfficerWorkflowStorageError from error

    return serialize_application(updated_application)


async def update_application_interest_rate(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    payload: InterestRateUpdateRequest,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    """Override the interest rate on an application and recalculate its EMI.

    Admin-only per the project settings. Recomputes monthly EMI, total interest,
    total repayment and the affordability recommendation, and stores the new
    ``interest_rate_used`` on the application.
    """
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise OfficerApplicationNotFoundError

    emi_fields = compute_emi_fields(
        requested_loan_amount=application.get("requested_loan_amount"),
        interest_rate_used=payload.interest_rate,
        loan_duration_months=application.get("loan_duration_months"),
        existing_monthly_debt=application.get("existing_monthly_debt"),
        monthly_income=application.get("monthly_income"),
    )
    if not emi_fields:
        raise ApplicationIncompleteForRateError

    actor_id = get_actor_id(current_user)
    previous_rate = application.get("interest_rate_used")
    updates = {**emi_fields, "updated_at": datetime.now(UTC)}
    updated_application = await database["loan_applications"].find_one_and_update(
        {"_id": application["_id"]},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if updated_application is None:
        raise OfficerApplicationNotFoundError

    try:
        await create_audit_log(
            database=database,
            user_id=actor_id,
            action="application_interest_rate_updated",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "actor_role": UserRole.ADMIN.value,
                "previous_interest_rate": previous_rate,
                "new_interest_rate": payload.interest_rate,
                "monthly_emi": emi_fields.get("monthly_emi"),
                "affordability": emi_fields.get("affordability"),
            },
        )
    except AuditLogStorageError as error:
        raise OfficerWorkflowStorageError from error

    return serialize_application(updated_application)


async def update_verification_checklist(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    payload: OfficerVerificationUpdate,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    """Merge officer verification sign-offs into the application's record."""
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise OfficerApplicationNotFoundError

    flags = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    verification = dict(application.get("verification") or {})
    verification.update(flags)

    updated_application = await database["loan_applications"].find_one_and_update(
        {"_id": application["_id"]},
        {"$set": {"verification": verification, "updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )
    if updated_application is None:
        raise OfficerApplicationNotFoundError

    try:
        await create_audit_log(
            database=database,
            user_id=get_actor_id(current_user),
            action="verification_checklist_updated",
            entity_type="loan_application",
            entity_id=application_id,
            details={"verification": verification},
        )
    except AuditLogStorageError as error:
        raise OfficerWorkflowStorageError from error

    return serialize_application(updated_application)


async def request_additional_documents(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    payload: AdditionalDocumentRequestCreate,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    application = await get_application_by_id(database, application_id)
    if application is None:
        raise OfficerApplicationNotFoundError

    actor_id = get_actor_id(current_user)
    try:
        document_request = await create_document_request(
            database=database,
            application_id=application_id,
            requested_by=actor_id,
            document_types=payload.document_types,
            message=payload.message,
        )
        updated_application = await update_application_status(
            database,
            application_id,
            ApplicationStatus.DOCUMENT_REQUESTED,
        )
        if updated_application is None:
            raise OfficerApplicationNotFoundError

        await create_audit_log(
            database=database,
            user_id=actor_id,
            action="officer_status_updated",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "actor_role": UserRole.OFFICER.value,
                "previous_status": str(application.get("status")),
                "new_status": ApplicationStatus.DOCUMENT_REQUESTED.value,
                "note": payload.message,
                "document_request_id": str(document_request["_id"]),
                "document_types": [
                    document_type.value for document_type in payload.document_types
                ],
            },
        )
        await create_notification(
            database=database,
            user_id=str(application.get("applicant_id")),
            title="Additional document requested",
            message=payload.message
            or "A loan officer requested additional documents for your application.",
        )
    except (
        AuditLogStorageError,
        DocumentRequestStorageError,
        NotificationStorageError,
    ) as error:
        raise OfficerWorkflowStorageError from error

    return document_request
