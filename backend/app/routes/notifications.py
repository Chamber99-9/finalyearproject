from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, get_current_user
from app.database import get_database
from app.schemas.notification import NotificationResponse
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationStorageError,
    list_user_notifications,
    mark_notification_read,
    serialize_notification,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/my", response_model=list[NotificationResponse])
async def read_my_notifications(
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    user_id = get_authenticated_user_id(current_user)
    notifications = await list_user_notifications(database, user_id)
    return [serialize_notification(notification) for notification in notifications]


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_my_notification_read(
    notification_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    user_id = get_authenticated_user_id(current_user)
    try:
        notification = await mark_notification_read(database, notification_id, user_id)
    except NotificationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        ) from error
    except NotificationStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update notification.",
        ) from error

    return serialize_notification(notification)
