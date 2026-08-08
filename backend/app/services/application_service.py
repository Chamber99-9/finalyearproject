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
from app.services.loan_rate_service import effective_rate_value
from app.services.loan_eligibility_service import (
    max_loan_amount,
    minimum_loan_amount,
    requires_collateral,
)
from app.services.loan_account_service import create_loan_account_for_application
from app.services.document_service import list_documents_for_application

APPLICATIONS_COLLECTION = "loan_applications"

# Collateral-backed loans must be supported by the collateral document
# (the land-ownership / property paper). This is the single mandatory collateral
# document — the valuation report and others are no longer compulsory.
COLLATERAL_REQUIRED_DOCUMENTS = ("property_papers",)


class ApplicationNotFoundError(Exception):
    pass


class ApplicationStatusError(Exception):
    pass


class IncompleteApplicationError(Exception):
    pass


class LoanAmountExceedsCapError(Exception):
    """Requested amount exceeds the salary-based cap for the loan type."""

    def __init__(self, max_amount: float) -> None:
        super().__init__("Requested amount exceeds the salary-based cap.")
        self.max_amount = max_amount


class LoanAmountBelowMinimumError(Exception):
    """Requested amount is below the minimum for the loan type (non-instant)."""

    def __init__(self, min_amount: float) -> None:
        super().__init__("Requested amount is below the minimum for this loan type.")
        self.min_amount = min_amount


class CollateralRequiredError(Exception):
    """Every non-instant loan needs collateral pledged."""


class CollateralDocumentsMissingError(Exception):
    """Collateral loans need an account statement and property papers uploaded."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__("Collateral documents are missing.")
        self.missing = missing


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

    # Resolve the effective rate (base + type spread + tenure) and freeze it.
    interest_rate_used = await effective_rate_value(
        database,
        loan_type=payload.loan_type.value,
        tenure=payload.loan_duration_months,
        tenure_unit="months",
    )
    document = create_application_document(
        applicant_id=applicant_id,
        payload=payload,
        interest_rate_used=interest_rate_used,
    )
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

    # Auto-calculate EMI + affordability before saving. The customer never sets
    # the rate: while the application is still a draft we (re)apply the current
    # bank-defined rate for this loan type. It freezes at submission, so a later
    # change to the bank default never alters submitted applications.
    effective = {**application, **updates}
    loan_type = str(effective.get("loan_type") or "personal")
    tenure_months = effective.get("loan_duration_months")
    interest_rate_used = None
    if tenure_months not in (None, ""):
        interest_rate_used = await effective_rate_value(
            database,
            loan_type=loan_type,
            tenure=int(tenure_months),
            tenure_unit="months",
        )
    updates.update(
        compute_emi_fields(
            requested_loan_amount=effective.get("requested_loan_amount"),
            interest_rate_used=interest_rate_used,
            loan_duration_months=tenure_months,
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

    # Salary-based cap + collateral rules (Phase 2).
    loan_type = str(application.get("loan_type") or "personal")
    amount = float(application.get("requested_loan_amount") or 0)
    income = float(application.get("monthly_income") or 0)
    minimum = minimum_loan_amount(loan_type)
    if minimum > 0 and amount < minimum:
        raise LoanAmountBelowMinimumError(minimum)
    cap = max_loan_amount(loan_type, income)
    if cap <= 0 or amount > cap:
        raise LoanAmountExceedsCapError(cap)
    if requires_collateral(loan_type, amount):
        # Secured loans just need the collateral document uploaded — no separate
        # collateral type/value is asked anymore.
        documents = await list_documents_for_application(database, application_id)
        uploaded_types = {str(document.get("document_type")) for document in documents}
        missing = [
            document_type
            for document_type in COLLATERAL_REQUIRED_DOCUMENTS
            if document_type not in uploaded_types
        ]
        if missing:
            raise CollateralDocumentsMissingError(missing)

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
    updates: dict[str, Any] = {
        "status": new_status.value,
        "offer_status": "accepted" if accepted else "declined",
        "offer_responded_at": now,
        "updated_at": now,
    }

    if accepted:
        # Accepting the counter offer makes the OFFERED amount the loan amount.
        # Re-price the EMI on that amount (the frozen interest rate is unchanged)
        # so the disbursed loan account matches what the customer agreed to —
        # previously the original requested amount/EMI was disbursed by mistake.
        offered_amount = application.get("offered_loan_amount")
        if offered_amount is not None:
            updates["requested_loan_amount"] = offered_amount
            updates.update(
                compute_emi_fields(
                    requested_loan_amount=offered_amount,
                    interest_rate_used=application.get("interest_rate_used"),
                    loan_duration_months=application.get("loan_duration_months"),
                    existing_monthly_debt=application.get("existing_monthly_debt"),
                    monthly_income=application.get("monthly_income"),
                )
            )

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

    # Accepting a counter offer approves the loan — open its loan account.
    if accepted:
        await create_loan_account_for_application(database, updated_application)

    return updated_application
