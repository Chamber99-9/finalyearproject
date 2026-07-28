from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.notification import (
    create_notification_document,
    notification_id_to_str,
)
from app.models.user import UserRole
from app.services.user_service import USERS_COLLECTION

NOTIFICATIONS_COLLECTION = "notifications"


class NotificationStorageError(Exception):
    pass


class NotificationNotFoundError(Exception):
    pass


def serialize_notification(document: dict[str, Any]) -> dict[str, Any]:
    return notification_id_to_str(document)


async def create_notification(
    *,
    database: AsyncIOMotorDatabase,
    user_id: str,
    title: str,
    message: str,
) -> dict[str, Any]:
    document = create_notification_document(
        user_id=user_id,
        title=title,
        message=message,
    )

    try:
        result = await database[NOTIFICATIONS_COLLECTION].insert_one(document)
    except Exception as error:
        raise NotificationStorageError from error

    document["_id"] = result.inserted_id
    return document


async def create_notifications_for_role(
    *,
    database: AsyncIOMotorDatabase,
    role: UserRole,
    title: str,
    message: str,
) -> list[dict[str, Any]]:
    users_cursor = database[USERS_COLLECTION].find({"role": role.value})
    notifications: list[dict[str, Any]] = []

    try:
        async for user in users_cursor:
            user_id = str(user.get("_id") or user.get("id"))
            if not user_id:
                continue
            notification = await create_notification(
                database=database,
                user_id=user_id,
                title=title,
                message=message,
            )
            notifications.append(notification)
    except Exception as error:
        raise NotificationStorageError from error

    return notifications


async def list_user_notifications(
    database: AsyncIOMotorDatabase,
    user_id: str,
) -> list[dict[str, Any]]:
    cursor = database[NOTIFICATIONS_COLLECTION].find({"user_id": user_id}).sort(
        "created_at",
        -1,
    )
    return [document async for document in cursor]


async def mark_notification_read(
    database: AsyncIOMotorDatabase,
    notification_id: str,
    user_id: str,
) -> dict[str, Any]:
    if not ObjectId.is_valid(notification_id):
        raise NotificationNotFoundError

    try:
        notification = await database[NOTIFICATIONS_COLLECTION].find_one_and_update(
            {
                "_id": ObjectId(notification_id),
                "user_id": user_id,
            },
            {"$set": {"read": True}},
            return_document=ReturnDocument.AFTER,
        )
    except Exception as error:
        raise NotificationStorageError from error

    if notification is None:
        raise NotificationNotFoundError
    return notification
