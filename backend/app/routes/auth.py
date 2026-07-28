from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, verify_password
from app.config import get_settings
from app.database import get_database
from app.schemas.user import TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from app.services.audit_service import AuditLogStorageError, create_audit_log
from app.services.user_service import (
    DuplicateUserError,
    create_customer_user,
    get_user_by_email,
    serialize_user,
)
from app.utilities.rate_limit import RateLimitExceededError, enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_auth_rate_limit(*, request: Request, action: str, email: str | None = None) -> None:
    client_ip = get_client_ip(request)
    keys = [f"auth:{action}:ip:{client_ip}"]
    if email:
        keys.append(f"auth:{action}:email:{email.lower().strip()}")

    try:
        for key in keys:
            enforce_rate_limit(
                key=key,
                limit=settings.auth_rate_limit_count,
                window_seconds=settings.auth_rate_limit_window_seconds,
            )
    except RateLimitExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
        ) from error


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    request: Request,
    payload: UserRegisterRequest,
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    enforce_auth_rate_limit(request=request, action="register", email=str(payload.email))

    try:
        user = await create_customer_user(database, payload)
    except DuplicateUserError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with this {error.field} already exists",
        ) from error

    public_user = serialize_user(user)
    try:
        await create_audit_log(
            database=database,
            user_id=public_user["id"],
            action="user_registered",
            entity_type="user",
            entity_id=public_user["id"],
            details={
                "role": public_user["role"],
                "email": public_user["email"],
            },
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User registered, but audit log could not be created.",
        ) from error

    return public_user


@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: Request,
    payload: UserLoginRequest,
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    normalized_email = str(payload.email).lower().strip()
    enforce_auth_rate_limit(request=request, action="login", email=normalized_email)

    user = await get_user_by_email(database, payload.email)
    password_hash = user.get("password_hash") if user else None
    if (
        user is None
        or not isinstance(password_hash, str)
        or not verify_password(payload.password, password_hash)
    ):
        try:
            await create_audit_log(
                database=database,
                user_id=str(user.get("_id") or user.get("id") or "unknown")
                if user
                else "unknown",
                action="user_login_failed",
                entity_type="auth",
                entity_id=normalized_email,
                details={
                    "email": normalized_email,
                    "client_ip": get_client_ip(request),
                },
            )
        except AuditLogStorageError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed, and audit log could not be created.",
            ) from error

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("is_blacklisted"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are blacklisted or your account has a problem right now. "
                "Please contact the bank."
            ),
        )

    public_user = serialize_user(user)
    try:
        await create_audit_log(
            database=database,
            user_id=public_user["id"],
            action="user_logged_in",
            entity_type="user",
            entity_id=public_user["id"],
            details={
                "role": public_user["role"],
                "email": public_user["email"],
            },
        )
    except AuditLogStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login succeeded, but audit log could not be created.",
        ) from error

    return {
        "access_token": create_access_token(public_user["id"]),
        "token_type": "bearer",
        "user": public_user,
    }


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    return serialize_user(current_user)
