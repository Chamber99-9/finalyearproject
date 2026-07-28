"""KYC lifecycle: customer submission, automated checks, officer/admin review."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.schemas.kyc import KycReviewRequest, KycSubmitRequest
from app.services.verification_service import verify_pan

KYC_COLLECTION = "kyc_records"
USERS_COLLECTION = "users"

# KYC statuses stored on the record and mirrored onto the user.
STATUS_PENDING = "pending"
STATUS_VERIFIED = "verified"
STATUS_REJECTED = "rejected"


class KycNotFoundError(Exception):
    pass


def serialize_kyc(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document


def _run_auto_checks(payload: KycSubmitRequest) -> dict[str, Any]:
    """Automated (mock/heuristic) checks that assist the officer's decision."""
    pan_result = verify_pan(payload.pan_number)
    return {
        "pan_valid_format": pan_result["valid_format"],
        "pan_tax_registered": pan_result["tax_registered"],
        "citizenship_provided": bool(payload.citizenship_number.strip()),
        "name_provided": len(payload.full_name.strip()) >= 2,
        "dob_provided": bool(payload.date_of_birth.strip()),
    }


async def _set_user_kyc_status(
    database: AsyncIOMotorDatabase,
    user_id: str,
    status: str,
) -> None:
    query = {"_id": ObjectId(user_id)} if ObjectId.is_valid(user_id) else {"_id": user_id}
    await database[USERS_COLLECTION].update_one(query, {"$set": {"kyc_status": status}})


async def submit_kyc(
    database: AsyncIOMotorDatabase,
    user_id: str,
    payload: KycSubmitRequest,
) -> dict[str, Any]:
    """Create/replace the user's KYC record, run auto-checks, mark pending review."""
    now = datetime.now(UTC)
    checks = _run_auto_checks(payload)
    document = {
        "user_id": user_id,
        "full_name": payload.full_name.strip(),
        "pan_number": payload.pan_number.strip(),
        "citizenship_number": payload.citizenship_number.strip(),
        "date_of_birth": payload.date_of_birth.strip(),
        "status": STATUS_PENDING,
        "checks": checks,
        "review_note": None,
        "created_at": now,
        "updated_at": now,
    }
    updated = await database[KYC_COLLECTION].find_one_and_update(
        {"user_id": user_id},
        {"$set": document},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    await _set_user_kyc_status(database, user_id, STATUS_PENDING)
    return updated


async def get_kyc_for_user(
    database: AsyncIOMotorDatabase,
    user_id: str,
) -> dict[str, Any] | None:
    return await database[KYC_COLLECTION].find_one({"user_id": user_id})


async def list_pending_kyc(database: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    cursor = database[KYC_COLLECTION].find({"status": STATUS_PENDING}).sort("created_at", -1)
    return [document async for document in cursor]


async def review_kyc(
    database: AsyncIOMotorDatabase,
    user_id: str,
    payload: KycReviewRequest,
) -> dict[str, Any]:
    """Officer/admin approves or rejects a KYC submission."""
    record = await database[KYC_COLLECTION].find_one({"user_id": user_id})
    if record is None:
        raise KycNotFoundError

    status = STATUS_VERIFIED if payload.approved else STATUS_REJECTED
    updated = await database[KYC_COLLECTION].find_one_and_update(
        {"user_id": user_id},
        {
            "$set": {
                "status": status,
                "review_note": payload.note,
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    await _set_user_kyc_status(database, user_id, status)
    return updated
