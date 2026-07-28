from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.application import (
    ApplicationStatus,
    application_id_to_str,
    compute_emi_fields,
    create_application_document,
    create_application_draft_document,
)
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationDraftCreateRequest,
    ApplicationUpdateRequest,
)

APPLICATIONS_COLLECTION = "loan_applications"


class ApplicationNotFoundError(Exception):
    pass


class ApplicationStatusError(Exception):
    pass


class IncompleteApplicationError(Exception):
    pass


def serialize_application(document: dict[str, Any]) -> dict[str, Any]:
    return application_id_to_str(document)


def _payload_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, str):
        return value.strip()
    return value


def _complete_application_payload(application: dict[str, Any]) -> ApplicationCreateRequest:
    try:
        return ApplicationCreateRequest.model_validate(application)
    except Exception as error:
        raise IncompleteApplicationError from error


async def create_empty_draft_application(
    database: AsyncIOMotorDatabase,
    applicant_id: str,
    payload: ApplicationDraftCreateRequest,
) -> dict[str, Any]:
    existing_draft = await database[APPLICATIONS_COLLECTION].find_one(
        {
            "applicant_id": applicant_id,
            "loan_type": payload.loan_type.value,
            "status": ApplicationStatus.DRAFT.value,
        },
        sort=[("created_at", -1)],
    )
    if existing_draft is not None:
        return existing_draft

    document = create_application_draft_document(
        applicant_id=applicant_id,
        loan_type=payload.loan_type,
    )
    result = await database[APPLICATIONS_COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def create_draft_application(
    database: AsyncIOMotorDatabase,
    applicant_id: str,
    payload: ApplicationCreateRequest,
) -> dict[str, Any]:
    existing_draft = await database[APPLICATIONS_COLLECTION].find_one(
        {
            "applicant_id": applicant_id,
            "citizenship_number": payload.citizenship_number.strip(),
            "status": ApplicationStatus.DRAFT.value,
        },
        sort=[("created_at", -1)],
    )
    if existing_draft is not None:
        return existing_draft

    document = create_application_document(applicant_id=applicant_id, payload=payload)
    result = await database[APPLICATIONS_COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def list_customer_applications(
    database: AsyncIOMotorDatabase,
    applicant_id: str,
) -> list[dict[str, Any]]:
    cursor = database[APPLICATIONS_COLLECTION].find({"applicant_id": applicant_id}).sort(
        "created_at",
        -1,
    )
    applications: list[dict[str, Any]] = []
    seen_draft_citizenship_numbers: set[str] = set()

    async for document in cursor:
        citizenship_number = str(document.get("citizenship_number") or "").strip()
        if (
            document.get("status") == ApplicationStatus.DRAFT.value
            and citizenship_number
        ):
            if citizenship_number in seen_draft_citizenship_numbers:
                continue
            seen_draft_citizenship_numbers.add(citizenship_number)

        applications.append(document)

    return applications


async def list_officer_applications(
    database: AsyncIOMotorDatabase,
) -> list[dict[str, Any]]:
    cursor = database[APPLICATIONS_COLLECTION].find(
        {"status": {"$ne": ApplicationStatus.DRAFT.value}}
    ).sort(
        "created_at",
        -1,
    )
    return [document async for document in cursor]


async def count_applications(database: AsyncIOMotorDatabase) -> int:
    return await database[APPLICATIONS_COLLECTION].count_documents({})


async def count_pending_applications(database: AsyncIOMotorDatabase) -> int:
    return await database[APPLICATIONS_COLLECTION].count_documents(
        {
            "status": {
                "$in": [
                    ApplicationStatus.SUBMITTED.value,
                    ApplicationStatus.UNDER_REVIEW.value,
                    ApplicationStatus.DOCUMENT_REQUESTED.value,
                    ApplicationStatus.COUNTER_OFFERED.value,
                ]
            }
        }
    )


async def get_owned_application(
    database: AsyncIOMotorDatabase,
    application_id: str,
    applicant_id: str,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(application_id):
        return None

    return await database[APPLICATIONS_COLLECTION].find_one(
        {
            "_id": ObjectId(application_id),
            "applicant_id": applicant_id,
        }
    )


async def get_application_by_id(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(application_id):
        return None

    return await database[APPLICATIONS_COLLECTION].find_one(
        {"_id": ObjectId(application_id)}
    )


async def update_application_status(
    database: AsyncIOMotorDatabase,
    application_id: str,
    new_status: ApplicationStatus,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(application_id):
        return None

    return await database[APPLICATIONS_COLLECTION].find_one_and_update(
        {"_id": ObjectId(application_id)},
        {
            "$set": {
                "status": new_status.value,
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )


async def update_owned_application(
    database: AsyncIOMotorDatabase,
    application_id: str,
    applicant_id: str,
    payload: ApplicationUpdateRequest,
) -> dict[str, Any]:
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise ApplicationNotFoundError

    if application.get("status") != ApplicationStatus.DRAFT.value:
        raise ApplicationStatusError

    updates = {
        key: _payload_value(value)
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }

    # Auto-calculate EMI + affordability before saving (requirements #3, #4, #7, #9).
    # Merge the incoming updates over the stored document so EMI reflects the
    # latest amount / rate / tenure / income, even if only some were edited.
    effective = {**application, **updates}
    updates.update(
        compute_emi_fields(
            requested_loan_amount=effective.get("requested_loan_amount"),
            annual_interest_rate=effective.get("annual_interest_rate"),
            loan_duration_months=effective.get("loan_duration_months"),
            existing_monthly_debt=effective.get("existing_monthly_debt"),
            monthly_income=effective.get("monthly_income"),
        )
    )

    updates["updated_at"] = datetime.now(UTC)

    updated_application = await database[APPLICATIONS_COLLECTION].find_one_and_update(
        {
            "_id": application["_id"],
            "applicant_id": applicant_id,
        },
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )

    if updated_application is None:
        raise ApplicationNotFoundError
    return updated_application


async def submit_owned_application(
    database: AsyncIOMotorDatabase,
    application_id: str,
    applicant_id: str,
) -> dict[str, Any]:
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise ApplicationNotFoundError

    if application.get("status") != ApplicationStatus.DRAFT.value:
        raise ApplicationStatusError

    _complete_application_payload(application)

    updated_application = await database[APPLICATIONS_COLLECTION].find_one_and_update(
        {
            "_id": application["_id"],
            "applicant_id": applicant_id,
        },
        {
            "$set": {
                "status": ApplicationStatus.SUBMITTED.value,
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if updated_application is None:
        raise ApplicationNotFoundError
    return updated_application


async def respond_to_counter_offer(
    database: AsyncIOMotorDatabase,
    application_id: str,
    applicant_id: str,
    accepted: bool,
) -> dict[str, Any]:
    application = await get_owned_application(database, application_id, applicant_id)
    if application is None:
        raise ApplicationNotFoundError

    if (
        application.get("status") != ApplicationStatus.COUNTER_OFFERED.value
        or application.get("offer_status") != "pending"
    ):
        raise ApplicationStatusError

    now = datetime.now(UTC)
    new_status = ApplicationStatus.APPROVED if accepted else ApplicationStatus.REJECTED
    updated_application = await database[APPLICATIONS_COLLECTION].find_one_and_update(
        {
            "_id": application["_id"],
            "applicant_id": applicant_id,
        },
        {
            "$set": {
                "status": new_status.value,
                "offer_status": "accepted" if accepted else "declined",
                "offer_responded_at": now,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if updated_application is None:
        raise ApplicationNotFoundError
    return updated_application
