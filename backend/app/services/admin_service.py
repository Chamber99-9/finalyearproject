from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import UserRole
from app.services.application_service import (
    count_applications,
    count_pending_applications,
)
from app.services.audit_service import (
    AuditLogStorageError,
    create_audit_log,
    list_audit_logs,
    serialize_audit_log,
)
from app.services.notification_service import (
    NotificationStorageError,
    create_notification,
)
from app.services.user_service import (
    count_admin_users,
    count_users,
    get_user_by_id,
    list_users,
    serialize_user,
    update_user_role,
)


class AdminUserNotFoundError(Exception):
    pass


class AdminUserUpdateError(Exception):
    pass


class AdminRoleChangeNotAllowedError(Exception):
    pass


async def get_admin_overview(database: AsyncIOMotorDatabase) -> dict[str, int]:
    return {
        "total_users": await count_users(database),
        "total_applications": await count_applications(database),
        "pending_applications": await count_pending_applications(database),
    }


async def list_admin_users(database: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    users = await list_users(database)
    return [serialize_user(user) for user in users]


async def update_admin_user_role(
    database: AsyncIOMotorDatabase,
    user_id: str,
    role: UserRole,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    existing_user = await get_user_by_id(database, user_id)
    if existing_user is None:
        raise AdminUserNotFoundError

    admin_user_id = str(current_user.get("_id") or current_user.get("id"))
    old_role = existing_user.get("role")
    if old_role == UserRole.ADMIN.value and role != UserRole.ADMIN:
        if user_id == admin_user_id:
            raise AdminRoleChangeNotAllowedError(
                "Admins cannot remove their own admin role."
            )
        if await count_admin_users(database) <= 1:
            raise AdminRoleChangeNotAllowedError(
                "At least one admin user must remain."
            )

    user = await update_user_role(database, user_id, role)
    if user is None:
        raise AdminUserUpdateError

    try:
        await create_audit_log(
            database=database,
            user_id=admin_user_id,
            action="admin_role_updated",
            entity_type="user",
            entity_id=user_id,
            details={
                "actor_role": UserRole.ADMIN.value,
                "target_user_id": user_id,
                "target_email": user.get("email"),
                "old_role": old_role,
                "new_role": user.get("role"),
            },
        )
        await create_notification(
            database=database,
            user_id=user_id,
            title="Account role updated",
            message=f"Your Sajilo Loan account role was changed to {user.get('role')}.",
        )
    except (AuditLogStorageError, NotificationStorageError) as error:
        raise AdminUserUpdateError from error

    return serialize_user(user)


async def list_admin_audit_logs(database: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    audit_logs = await list_audit_logs(database)
    return [serialize_audit_log(audit_log) for audit_log in audit_logs]
