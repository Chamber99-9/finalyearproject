from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId

from app.models.document import DocumentType


class DocumentRequestStatus(StrEnum):
    OPEN = "open"


def create_document_request_document(
    *,
    application_id: str,
    requested_by: str,
    document_types: list[DocumentType],
    message: str | None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "application_id": application_id,
        "requested_by": requested_by,
        "document_types": [document_type.value for document_type in document_types],
        "message": message.strip() if message else None,
        "status": DocumentRequestStatus.OPEN.value,
        "created_at": now,
        "updated_at": now,
    }


def document_request_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document
