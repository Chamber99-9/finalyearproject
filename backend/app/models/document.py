from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId


class DocumentType(StrEnum):
    CITIZENSHIP_DOCUMENT = "citizenship_document"
    SALARY_SLIP = "salary_slip"
    BANK_STATEMENT = "bank_statement"
    SUPPORTING_DOCUMENT = "supporting_document"


def create_document_metadata(
    *,
    application_id: str,
    user_id: str,
    document_type: DocumentType,
    filename: str,
    file_path: str,
    content_type: str,
    file_hash: str,
) -> dict[str, Any]:
    return {
        "application_id": application_id,
        "user_id": user_id,
        "document_type": document_type.value,
        "filename": filename,
        "file_path": file_path,
        "content_type": content_type,
        "file_hash": file_hash,
        "uploaded_at": datetime.now(UTC),
    }


def document_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document

