from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.audit import audit_log_id_to_str, create_audit_log_document

AUDIT_LOGS_COLLECTION = "audit_logs"


class AuditLogStorageError(Exception):
    pass


def serialize_audit_log(document: dict[str, Any]) -> dict[str, Any]:
    audit_log = audit_log_id_to_str(document)

    if "user_id" not in audit_log:
        audit_log["user_id"] = str(audit_log.get("actor_id") or "")

    details = audit_log.get("details")
    if not isinstance(details, dict):
        details = {}

    legacy_metadata = audit_log.get("metadata")
    if isinstance(legacy_metadata, dict):
        details.update(legacy_metadata)

    for key in ("actor_role", "previous_status", "new_status", "note"):
        value = audit_log.get(key)
        if value is not None and key not in details:
            details[key] = value

    audit_log["details"] = details
    audit_log.pop("actor_id", None)
    audit_log.pop("actor_role", None)
    audit_log.pop("previous_status", None)
    audit_log.pop("new_status", None)
    audit_log.pop("note", None)
    audit_log.pop("metadata", None)
    return audit_log


async def list_audit_logs(database: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    cursor = database[AUDIT_LOGS_COLLECTION].find({}).sort("created_at", -1)
    return [document async for document in cursor]


async def create_audit_log(
    *,
    database: AsyncIOMotorDatabase,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = create_audit_log_document(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )

    try:
        result = await database[AUDIT_LOGS_COLLECTION].insert_one(document)
    except Exception as error:
        raise AuditLogStorageError from error

    document["_id"] = result.inserted_id
    return document
