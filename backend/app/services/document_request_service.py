from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.document import DocumentType
from app.models.document_request import (
    create_document_request_document,
    document_request_id_to_str,
)

DOCUMENT_REQUESTS_COLLECTION = "application_document_requests"


class DocumentRequestStorageError(Exception):
    pass


def serialize_document_request(document: dict[str, Any]) -> dict[str, Any]:
    return document_request_id_to_str(document)


async def create_document_request(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    requested_by: str,
    document_types: list[DocumentType],
    message: str | None,
) -> dict[str, Any]:
    document = create_document_request_document(
        application_id=application_id,
        requested_by=requested_by,
        document_types=document_types,
        message=message,
    )

    try:
        result = await database[DOCUMENT_REQUESTS_COLLECTION].insert_one(document)
    except Exception as error:
        raise DocumentRequestStorageError from error

    document["_id"] = result.inserted_id
    return document


async def get_latest_open_document_request(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> dict[str, Any] | None:
    return await database[DOCUMENT_REQUESTS_COLLECTION].find_one(
        {
            "application_id": application_id,
            "status": "open",
        },
        sort=[("created_at", -1)],
    )
