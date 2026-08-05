from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.auth.security import hash_password
from app.models.user import UserRole, create_user_document, document_id_to_str
from app.schemas.user import UserRegisterRequest

USERS_COLLECTION = "users"


class DuplicateUserError(Exception):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"User with this {field} already exists")


def normalize_email(email: str) -> str:
    return email.lower().strip()


def serialize_user(document: dict[str, Any]) -> dict[str, Any]:
    user = document_id_to_str(document)
    user.pop("password_hash", None)
    return user


async def list_users(database: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    cursor = database[USERS_COLLECTION].find({}).sort("created_at", -1)
    return [document async for document in cursor]


async def count_users(database: AsyncIOMotorDatabase) -> int:
    return await database[USERS_COLLECTION].count_documents({})


async def count_admin_users(database: AsyncIOMotorDatabase) -> int:
    return await database[USERS_COLLECTION].count_documents(
        {"role": UserRole.ADMIN.value}
    )


async def get_user_by_email(
    database: AsyncIOMotorDatabase,
    email: str,
) -> dict[str, Any] | None:
    return await database[USERS_COLLECTION].find_one({"email": normalize_email(email)})


async def get_user_by_phone(
    database: AsyncIOMotorDatabase,
    phone: str,
) -> dict[str, Any] | None:
    return await database[USERS_COLLECTION].find_one({"phone": phone.strip()})


async def get_user_by_id(
    database: AsyncIOMotorDatabase,
    user_id: str,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await database[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})


async def update_user_role(
    database: AsyncIOMotorDatabase,
    user_id: str,
    role: UserRole,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(user_id):
        return None

    return await database[USERS_COLLECTION].find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role.value}},
        return_document=ReturnDocument.AFTER,
    )


async def set_user_blacklist(
    database: AsyncIOMotorDatabase,
    user_id: str,
    blacklisted: bool,
) -> dict[str, Any] | None:
    """Manually blacklist (or clear) a user. A blacklisted user cannot log in."""
    if not ObjectId.is_valid(user_id):
        return None
    return await database[USERS_COLLECTION].find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_blacklisted": bool(blacklisted)}},
        return_document=ReturnDocument.AFTER,
    )


async def create_customer_user(
    database: AsyncIOMotorDatabase,
    payload: UserRegisterRequest,
) -> dict[str, Any]:
    if await get_user_by_email(database, payload.email):
        raise DuplicateUserError("email")
    if await get_user_by_phone(database, payload.phone):
        raise DuplicateUserError("phone")

    document = create_user_document(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=UserRole.CUSTOMER,
    )
    result = await database[USERS_COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    return document
