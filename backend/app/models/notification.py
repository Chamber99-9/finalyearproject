from datetime import UTC, datetime
from typing import Any

from bson import ObjectId


def create_notification_document(
    *,
    user_id: str,
    title: str,
    message: str,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "title": title.strip(),
        "message": message.strip(),
        "read": False,
        "created_at": datetime.now(UTC),
    }


def notification_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document
