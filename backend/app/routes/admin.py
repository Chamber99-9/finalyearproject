from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_admin
from app.database import get_database
from app.models.user import UserRole
from app.schemas.admin import (
    AdminOverviewResponse,
    AuditLogResponse,
    BillingRunResponse,
    BlacklistRequest,
    ClockAdvanceRequest,
    ClockResponse,
    UserRoleUpdateRequest,
)
from app.schemas.application import ApplicationResponse
from app.schemas.officer import InterestRateUpdateRequest
from app.schemas.payments import PaymentResponse
from app.schemas.user import UserResponse
from app.services.payment_service import list_payments_for_applicant, serialize_payment
from app.services.admin_service import (
    AdminUserNotFoundError,
    AdminRoleChangeNotAllowedError,
    AdminUserUpdateError,
    get_admin_overview,
    list_admin_audit_logs,
    list_admin_users,
    update_admin_user_role,
)
from app.services.audit_service import create_audit_log
from app.services.clock_service import (
    advance_days,
    get_offset_days,
    reset_clock,
    simulated_now,
)
from app.services.loan_account_service import process_due_reminders, process_overdue
from app.services.notification_service import create_notification
from app.services.user_service import serialize_user, set_user_blacklist
from app.services.officer_service import (
    ApplicationIncompleteForRateError,
    OfficerApplicationNotFoundError,
    OfficerWorkflowStorageError,
    list_review_applications,
    update_application_interest_rate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/applications", response_model=list[ApplicationResponse])
async def read_admin_applications(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    """List submitted applications for admin rate management."""
    return await list_review_applications(database)


@router.put(
    "/applications/{application_id}/interest-rate",
    response_model=ApplicationResponse,
)
async def override_application_interest_rate(
    application_id: str,
    payload: InterestRateUpdateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Override the interest rate on one application and recalculate its EMI."""
    try:
        return await update_application_interest_rate(
            database=database,
            application_id=application_id,
            payload=payload,
            current_user=current_user,
        )
    except OfficerApplicationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from error
    except ApplicationIncompleteForRateError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application is missing loan amount or tenure; cannot recalculate EMI.",
        ) from error
    except OfficerWorkflowStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the interest rate.",
        ) from error


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


@router.get("/users/{user_id}/statement", response_model=list[PaymentResponse])
async def read_user_statement(
    user_id: str,
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    """A customer's full payment statement history (every EMI / advance payment,
    with its receipt fields), newest first — admin only."""
    payments = await list_payments_for_applicant(database, user_id)
    return [serialize_payment(payment) for payment in payments]


# --- Blacklist control (admin) ---------------------------------------------

async def _apply_blacklist(
    database: AsyncIOMotorDatabase,
    user_id: str,
    blacklisted: bool,
    actor: dict,
) -> dict:
    updated = await set_user_blacklist(database, user_id, blacklisted)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    action = "user_blacklisted" if blacklisted else "user_unblacklisted"
    await create_audit_log(
        database=database,
        user_id=get_authenticated_user_id(actor),
        action=action,
        entity_type="user",
        entity_id=user_id,
        details={"actor_role": actor.get("role"), "blacklisted": blacklisted},
    )
    await create_notification(
        database=database,
        user_id=user_id,
        title="Account blacklisted" if blacklisted else "Account restored",
        message=(
            "Your account has been blacklisted. Please contact the bank."
            if blacklisted
            else "Your account has been restored. You can log in again."
        ),
    )
    return serialize_user(updated)


@router.put("/users/{user_id}/blacklist", response_model=UserResponse)
async def admin_blacklist_user(
    user_id: str,
    payload: BlacklistRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    return await _apply_blacklist(database, user_id, payload.blacklisted, current_user)


# --- Simulated clock / calendar (admin, for testing time features) ---------

@router.get("/clock", response_model=ClockResponse)
async def read_clock(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    return {
        "offset_days": await get_offset_days(database),
        "simulated_now": await simulated_now(database),
    }


@router.post("/clock/advance", response_model=ClockResponse)
async def advance_clock(
    payload: ClockAdvanceRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    await advance_days(database, payload.days)
    return {
        "offset_days": await get_offset_days(database),
        "simulated_now": await simulated_now(database),
    }


@router.post("/clock/reset", response_model=ClockResponse)
async def reset_clock_route(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    await reset_clock(database)
    return {
        "offset_days": await get_offset_days(database),
        "simulated_now": await simulated_now(database),
    }


@router.post("/run-billing", response_model=BillingRunResponse)
async def run_billing(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Run the daily billing jobs at the simulated date: EMI reminders (email +
    notification) and overdue processing (missed-installment counting +
    blacklisting). Lets you test time-based features without waiting a month."""
    try:
        reminders = await process_due_reminders(database)
    except Exception:  # noqa: BLE001 - never fail the whole run on reminders
        reminders = {"reminded": 0}
    try:
        overdue = await process_overdue(database)
    except Exception:  # noqa: BLE001 - never fail the whole run on overdue
        overdue = {"overdue": 0, "blacklisted": 0}
    return {
        "reminded": reminders.get("reminded", 0),
        "overdue": overdue.get("overdue", 0),
        "blacklisted": overdue.get("blacklisted", 0),
        "simulated_now": await simulated_now(database),
    }
