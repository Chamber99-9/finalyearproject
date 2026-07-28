from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import require_admin
from app.database import get_database
from app.schemas.admin import (
    AdminOverviewResponse,
    AuditLogResponse,
    UserRoleUpdateRequest,
)
from app.schemas.user import UserResponse
from app.services.admin_service import (
    AdminUserNotFoundError,
    AdminRoleChangeNotAllowedError,
    AdminUserUpdateError,
    get_admin_overview,
    list_admin_audit_logs,
    list_admin_users,
    update_admin_user_role,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
async def read_admin_overview(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    return await get_admin_overview(database)


@router.get("/users", response_model=list[UserResponse])
async def read_admin_users(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    return await list_admin_users(database)


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_admin_user_role_route(
    user_id: str,
    payload: UserRoleUpdateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    try:
        return await update_admin_user_role(database, user_id, payload.role, current_user)
    except AdminUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from error
    except AdminUserUpdateError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user role.",
        ) from error
    except AdminRoleChangeNotAllowedError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def read_admin_audit_logs(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    return await list_admin_audit_logs(database)
