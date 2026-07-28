from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId


class SuspicionLevel(StrEnum):
    LOW = "Low Suspicion"
    MEDIUM = "Medium Suspicion"
    HIGH = "High Suspicion"


class FlagSeverity(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"


class FlagCode(StrEnum):
    DUPLICATE_CITIZENSHIP_NUMBER = "DUPLICATE_CITIZENSHIP_NUMBER"
    NAME_MISMATCH = "NAME_MISMATCH"
    INCOME_MISMATCH = "INCOME_MISMATCH"
    BANK_STATEMENT_NAME_MISMATCH = "BANK_STATEMENT_NAME_MISMATCH"
    MISSING_REQUIRED_DOCUMENT = "MISSING_REQUIRED_DOCUMENT"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    DUPLICATE_DOCUMENT_HASH = "DUPLICATE_DOCUMENT_HASH"
    UNUSUAL_LOAN_AMOUNT = "UNUSUAL_LOAN_AMOUNT"


def create_flag_item(
    *,
    code: FlagCode,
    message: str,
    severity: FlagSeverity,
) -> dict[str, str]:
    return {
        "code": code.value,
        "message": message,
        "severity": severity.value,
    }


def create_application_flags_document(
    *,
    application_id: str,
    total_flags: int,
    suspicion_level: SuspicionLevel,
    flags: list[dict[str, str]],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "application_id": application_id,
        "total_flags": total_flags,
        "suspicion_level": suspicion_level.value,
        "flags": flags,
        "created_at": created_at or now,
        "updated_at": now,
    }


def application_flags_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document
