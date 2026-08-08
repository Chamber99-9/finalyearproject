from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.auth.security import decode_access_token
from app.database import get_database
from app.models.user import UserRole
from app.services.user_service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(database, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # A blacklisted user is signed out immediately: every authenticated request
    # is rejected as unauthorized, so their existing session stops working on the
    # very next action (the frontend then bounces them to the login page).
    if user.get("is_blacklisted"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been blacklisted. Please contact the bank.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_authenticated_user_id(current_user: dict) -> str:
    user_id = current_user.get("_id") or current_user.get("id")
    if isinstance(user_id, ObjectId):
        return str(user_id)
    if isinstance(user_id, str) and user_id:
        return user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authenticated user id is missing.",
    )


async def require_customer(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if current_user.get("role") != UserRole.CUSTOMER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access this route.",
        )
    return current_user


async def require_officer(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if current_user.get("role") != UserRole.OFFICER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only loan officers can access this route.",
        )
    return current_user


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this route.",
        )
    return current_user


async def require_officer_or_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if current_user.get("role") not in {UserRole.OFFICER.value, UserRole.ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only loan officers and admins can access this route.",
        )
    return current_user
