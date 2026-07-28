from datetime import UTC, datetime
from typing import Any


def create_audit_log_document(
    *,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {},
        "created_at": datetime.now(UTC),
    }


def audit_log_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if "_id" in document:
        document["id"] = str(document.pop("_id"))
    return document
