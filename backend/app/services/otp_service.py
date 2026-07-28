"""Email one-time-password (OTP) service for two-factor login."""

from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.security import generate_otp, hash_otp, verify_otp
from app.config import get_settings
from app.services.email_service import send_email

LOGIN_OTPS_COLLECTION = "login_otps"


class OTPError(Exception):
    """OTP is missing, expired, exhausted, or incorrect."""


async def create_login_otp(
    database: AsyncIOMotorDatabase,
    user: dict[str, Any],
) -> str:
    """Generate, store, and email a login OTP. Returns the OTP (for tests/dev)."""
    settings = get_settings()
    user_id = str(user.get("_id") or user.get("id"))

    # One active OTP per user — clear any previous ones.
    await database[LOGIN_OTPS_COLLECTION].delete_many({"user_id": user_id})

    otp = generate_otp(settings.otp_length)
    now = datetime.now(UTC)
    await database[LOGIN_OTPS_COLLECTION].insert_one(
        {
            "user_id": user_id,
            "otp_hash": hash_otp(otp),
            "attempts": 0,
            "expires_at": now + timedelta(minutes=settings.otp_expiry_minutes),
            "created_at": now,
        }
    )

    email = user.get("email")
    if email:
        await send_email(
            database=database,
            to_email=str(email),
            subject="Sajilo Loan — your login code",
            body=(
                f"Your Sajilo Loan login code is {otp}. "
                f"It expires in {settings.otp_expiry_minutes} minutes."
            ),
        )
    return otp


async def verify_login_otp(
    database: AsyncIOMotorDatabase,
    user_id: str,
    otp: str,
) -> None:
    """Verify a submitted OTP. Raises OTPError on any failure."""
    settings = get_settings()
    record = await database[LOGIN_OTPS_COLLECTION].find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    if record is None:
        raise OTPError("No login code was requested. Please sign in again.")

    if record.get("expires_at") and record["expires_at"] < datetime.now(UTC):
        await database[LOGIN_OTPS_COLLECTION].delete_many({"user_id": user_id})
        raise OTPError("Your login code has expired. Please sign in again.")

    if int(record.get("attempts", 0)) >= settings.otp_max_attempts:
        await database[LOGIN_OTPS_COLLECTION].delete_many({"user_id": user_id})
        raise OTPError("Too many incorrect attempts. Please sign in again.")

    if not verify_otp(otp, str(record.get("otp_hash", ""))):
        await database[LOGIN_OTPS_COLLECTION].update_one(
            {"_id": record["_id"]},
            {"$set": {"attempts": int(record.get("attempts", 0)) + 1}},
        )
        raise OTPError("Incorrect login code.")

    # Success — consume the OTP.
    await database[LOGIN_OTPS_COLLECTION].delete_many({"user_id": user_id})
