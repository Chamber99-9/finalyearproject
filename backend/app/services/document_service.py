import hashlib
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.document import (
    DocumentType,
    create_document_metadata,
    document_id_to_str,
)

DOCUMENTS_COLLECTION = "application_documents"
COMMON_REQUIRED_DOCUMENT_TYPES = {
    DocumentType.CITIZENSHIP_DOCUMENT.value,
    DocumentType.SALARY_SLIP.value,
    DocumentType.BANK_STATEMENT.value,
}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}


class EmptyUploadError(Exception):
    pass


class UnsupportedContentTypeError(Exception):
    pass


class FileStorageError(Exception):
    pass


class MetadataStorageError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "document").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "document"


def serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized_document = document_id_to_str(document)
    serialized_document.pop("file_path", None)
    return serialized_document


def validate_file_extension(*, filename: str, content_type: str) -> None:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS.get(content_type, set()):
        raise UnsupportedContentTypeError


def validate_file_signature(*, content_type: str, first_chunk: bytes) -> None:
    if content_type == "application/pdf" and not first_chunk.startswith(b"%PDF-"):
        raise UnsupportedContentTypeError
    if content_type == "image/jpeg" and not first_chunk.startswith(b"\xff\xd8\xff"):
        raise UnsupportedContentTypeError
    if content_type == "image/png" and not first_chunk.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        raise UnsupportedContentTypeError
    if content_type == "image/webp" and not (
        first_chunk.startswith(b"RIFF") and first_chunk[8:12] == b"WEBP"
    ):
        raise UnsupportedContentTypeError


def get_required_document_types_for_loan_type(_: str | None = None) -> set[str]:
    return set(COMMON_REQUIRED_DOCUMENT_TYPES)


async def get_document_by_id(
    database: AsyncIOMotorDatabase,
    document_id: str,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(document_id):
        return None

    return await database[DOCUMENTS_COLLECTION].find_one({"_id": ObjectId(document_id)})


async def list_documents_for_application(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> list[dict[str, Any]]:
    cursor = database[DOCUMENTS_COLLECTION].find({"application_id": application_id}).sort(
        "uploaded_at",
        -1,
    )
    return [document async for document in cursor]


async def find_duplicate_document_hash_for_other_user(
    *,
    database: AsyncIOMotorDatabase,
    file_hash: str,
    user_id: str,
    document_id: str,
) -> dict[str, Any] | None:
    query: dict[str, Any] = {
        "file_hash": file_hash,
        "user_id": {"$ne": user_id},
    }

    if ObjectId.is_valid(document_id):
        query["_id"] = {"$ne": ObjectId(document_id)}

    return await database[DOCUMENTS_COLLECTION].find_one(query)


async def save_application_document(
    *,
    database: AsyncIOMotorDatabase,
    application_id: str,
    user_id: str,
    document_type: DocumentType,
    file: UploadFile,
    upload_dir: str,
    max_upload_bytes: int,
) -> dict[str, Any]:
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedContentTypeError

    original_filename = sanitize_filename(file.filename or "document")
    validate_file_extension(filename=original_filename, content_type=content_type)

    storage_dir = Path(upload_dir) / "applications" / application_id / document_type.value
    stored_filename = f"{uuid4().hex}_{original_filename}"
    file_path = storage_dir / stored_filename
    file_hash = hashlib.sha256()
    bytes_written = 0
    first_chunk = b""

    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                if not first_chunk:
                    first_chunk = chunk
                    validate_file_signature(
                        content_type=content_type,
                        first_chunk=first_chunk,
                    )
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise FileTooLargeError
                file_hash.update(chunk)
                destination.write(chunk)
    except (FileTooLargeError, UnsupportedContentTypeError):
        file_path.unlink(missing_ok=True)
        raise
    except OSError as error:
        file_path.unlink(missing_ok=True)
        raise FileStorageError from error
    finally:
        await file.close()

    if bytes_written == 0:
        file_path.unlink(missing_ok=True)
        raise EmptyUploadError

    metadata = create_document_metadata(
        application_id=application_id,
        user_id=user_id,
        document_type=document_type,
        filename=original_filename,
        file_path=str(file_path),
        content_type=content_type,
        file_hash=file_hash.hexdigest(),
    )

    try:
        result = await database[DOCUMENTS_COLLECTION].insert_one(metadata)
    except Exception as error:
        file_path.unlink(missing_ok=True)
        raise MetadataStorageError from error

    metadata["_id"] = result.inserted_id
    return metadata
