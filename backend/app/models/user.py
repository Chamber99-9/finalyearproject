from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId


class UserRole(StrEnum):
    CUSTOMER = "customer"
    OFFICER = "officer"
    ADMIN = "admin"


def create_user_document(
    *,
    full_name: str,
    email: str,
    phone: str,
    password_hash: str,
    role: UserRole = UserRole.CUSTOMER,
) -> dict[str, Any]:
    return {
        "full_name": full_name.strip(),
        "email": email.lower().strip(),
        "phone": phone.strip(),
        "password_hash": password_hash,
        "role": role.value,
        "created_at": datetime.now(UTC),
    }


def document_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document

