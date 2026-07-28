import re
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.document import DocumentType
from app.models.flags import (
    FlagCode,
    FlagSeverity,
    SuspicionLevel,
    application_flags_id_to_str,
    create_application_flags_document,
    create_flag_item,
)
from app.services.application_service import APPLICATIONS_COLLECTION
from app.services.document_service import (
    find_duplicate_document_hash_for_other_user,
    get_required_document_types_for_loan_type,
    list_documents_for_application,
)
from app.services.ocr_service import get_latest_ocr_result_for_document

APPLICATION_FLAGS_COLLECTION = "application_flags"


class ApplicationFlagStorageError(Exception):
    pass


def serialize_application_flags(document: dict[str, Any]) -> dict[str, Any]:
    return application_flags_id_to_str(document)


def classify_suspicion(total_flags: int) -> SuspicionLevel:
    if total_flags == 0:
        return SuspicionLevel.LOW
    if total_flags <= 2:
        return SuspicionLevel.MEDIUM
    return SuspicionLevel.HIGH


def normalize_name(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[^\w\s]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def safe_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def latest_documents_by_type(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest_documents: dict[str, dict[str, Any]] = {}
    for document in sorted(
        documents,
        key=lambda item: item.get("uploaded_at") or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    ):
        document_type = document.get("document_type")
        if isinstance(document_type, str) and document_type not in latest_documents:
            latest_documents[document_type] = document
    return latest_documents


def verified_corrected_data(ocr_result: dict[str, Any] | None) -> dict[str, Any]:
    if not ocr_result or not ocr_result.get("verified_by_user"):
        return {}

    corrected_data = ocr_result.get("corrected_data")
    if not isinstance(corrected_data, dict):
        return {}
    return corrected_data


async def has_duplicate_citizenship_number(
    database: AsyncIOMotorDatabase,
    application: dict[str, Any],
) -> bool:
    citizenship_number = str(application.get("citizenship_number") or "").strip()
    if not citizenship_number:
        return False

    duplicate = await database[APPLICATIONS_COLLECTION].find_one(
        {
            "_id": {"$ne": application["_id"]},
            "citizenship_number": citizenship_number,
        }
    )
    return duplicate is not None


async def build_document_context(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    documents = await list_documents_for_application(database, application_id)
    documents_by_type = latest_documents_by_type(documents)
    ocr_by_document_id: dict[str, dict[str, Any]] = {}

    for document in documents:
        document_id = str(document.get("_id") or document.get("id"))
        if not document_id:
            continue

        ocr_result = await get_latest_ocr_result_for_document(database, document_id)
        if ocr_result is not None:
            ocr_by_document_id[document_id] = ocr_result

    return documents, documents_by_type, ocr_by_document_id


async def evaluate_application_flags(
    database: AsyncIOMotorDatabase,
    application: dict[str, Any],
) -> list[dict[str, str]]:
    application_id = str(application["_id"])
    applicant_id = str(application.get("applicant_id") or "")
    flags: list[dict[str, str]] = []

    documents, documents_by_type, ocr_by_document_id = await build_document_context(
        database,
        application_id,
    )

    if await has_duplicate_citizenship_number(database, application):
        flags.append(
            create_flag_item(
                code=FlagCode.DUPLICATE_CITIZENSHIP_NUMBER,
                message="Duplicate citizenship number found in another application",
                severity=FlagSeverity.MEDIUM,
            )
        )

    required_document_types = get_required_document_types_for_loan_type(
        str(application.get("loan_type") or "")
    )
    missing_document_types = sorted(required_document_types - set(documents_by_type))
    if missing_document_types:
        flags.append(
            create_flag_item(
                code=FlagCode.MISSING_REQUIRED_DOCUMENT,
                message=(
                    "Missing required documents: "
                    + ", ".join(missing_document_types)
                ),
                severity=FlagSeverity.HIGH,
            )
        )

    citizenship_document = documents_by_type.get(DocumentType.CITIZENSHIP_DOCUMENT.value)
    if citizenship_document is not None:
        ocr_result = ocr_by_document_id.get(
            str(citizenship_document.get("_id") or citizenship_document.get("id"))
        )
        citizenship_data = verified_corrected_data(ocr_result)
        citizenship_name = citizenship_data.get("full_name")
        if citizenship_name and normalize_name(citizenship_name) != normalize_name(
            application.get("full_name")
        ):
            flags.append(
                create_flag_item(
                    code=FlagCode.NAME_MISMATCH,
                    message="Applicant name does not match the citizenship document name",
                    severity=FlagSeverity.HIGH,
                )
            )

    salary_slip = documents_by_type.get(DocumentType.SALARY_SLIP.value)
    if salary_slip is not None:
        ocr_result = ocr_by_document_id.get(str(salary_slip.get("_id") or salary_slip.get("id")))
        salary_data = verified_corrected_data(ocr_result)
        salary_income = safe_number(salary_data.get("monthly_income"))
        form_income = safe_number(application.get("monthly_income"))
        if salary_income is not None and form_income and form_income > 0:
            income_difference = abs(form_income - salary_income) / form_income * 100
            if income_difference > 20:
                flags.append(
                    create_flag_item(
                        code=FlagCode.INCOME_MISMATCH,
                        message="Form income differs from salary slip income by more than 20%",
                        severity=FlagSeverity.HIGH,
                    )
                )

    bank_statement = documents_by_type.get(DocumentType.BANK_STATEMENT.value)
    if bank_statement is not None:
        ocr_result = ocr_by_document_id.get(
            str(bank_statement.get("_id") or bank_statement.get("id"))
        )
        bank_data = verified_corrected_data(ocr_result)
        account_holder_name = bank_data.get("account_holder_name")
        if account_holder_name and normalize_name(account_holder_name) != normalize_name(
            application.get("full_name")
        ):
            flags.append(
                create_flag_item(
                    code=FlagCode.BANK_STATEMENT_NAME_MISMATCH,
                    message="Bank statement account holder name does not match applicant name",
                    severity=FlagSeverity.HIGH,
                )
            )

    if any(
        result.get("confidence_score") is not None
        and safe_number(result.get("confidence_score")) is not None
        and safe_number(result.get("confidence_score")) < 75
        for result in ocr_by_document_id.values()
    ):
        flags.append(
            create_flag_item(
                code=FlagCode.LOW_OCR_CONFIDENCE,
                message="OCR confidence score is below 75%",
                severity=FlagSeverity.MEDIUM,
            )
        )

    for document in documents:
        file_hash = str(document.get("file_hash") or "")
        if not file_hash:
            continue

        duplicate = await find_duplicate_document_hash_for_other_user(
            database=database,
            file_hash=file_hash,
            user_id=applicant_id,
            document_id=str(document.get("_id") or document.get("id")),
        )
        if duplicate is not None:
            flags.append(
                create_flag_item(
                    code=FlagCode.DUPLICATE_DOCUMENT_HASH,
                    message="Same document hash has been uploaded by multiple users",
                    severity=FlagSeverity.HIGH,
                )
            )
            break

    monthly_income = safe_number(application.get("monthly_income"))
    requested_loan_amount = safe_number(application.get("requested_loan_amount"))
    if (
        monthly_income is not None
        and monthly_income > 0
        and requested_loan_amount is not None
        and requested_loan_amount > monthly_income * 20
    ):
        flags.append(
            create_flag_item(
                code=FlagCode.UNUSUAL_LOAN_AMOUNT,
                message="Requested loan amount is greater than 20x monthly income",
                severity=FlagSeverity.MEDIUM,
            )
        )

    return flags


async def check_and_save_application_flags(
    database: AsyncIOMotorDatabase,
    application: dict[str, Any],
) -> dict[str, Any]:
    application_id = str(application["_id"])
    flags = await evaluate_application_flags(database, application)
    total_flags = len(flags)
    suspicion_level = classify_suspicion(total_flags)
    existing_result = await database[APPLICATION_FLAGS_COLLECTION].find_one(
        {"application_id": application_id}
    )
    document = create_application_flags_document(
        application_id=application_id,
        total_flags=total_flags,
        suspicion_level=suspicion_level,
        flags=flags,
        created_at=existing_result.get("created_at") if existing_result else None,
    )

    try:
        result = await database[APPLICATION_FLAGS_COLLECTION].find_one_and_update(
            {"application_id": application_id},
            {"$set": document},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except Exception as error:
        raise ApplicationFlagStorageError from error

    if result is None:
        raise ApplicationFlagStorageError
    return result


async def get_latest_application_flags(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> dict[str, Any] | None:
    return await database[APPLICATION_FLAGS_COLLECTION].find_one(
        {"application_id": application_id},
        sort=[("updated_at", -1)],
    )
