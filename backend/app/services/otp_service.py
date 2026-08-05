"""Email one-time-password (OTP) service.

Used for two purposes with one implementation: email verification at
registration, and opt-in two-factor login. Both flows generate, store, email,
and later verify a short numeric code tied to the user.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.security import generate_otp, hash_otp, verify_otp
from app.config import get_settings
from app.services.email_service import send_email

EMAIL_OTPS_COLLECTION = "email_otps"


class OTPError(Exception):
    """OTP is missing, expired, exhausted, or incorrect."""


async def create_email_otp(
    database: AsyncIOMotorDatabase,
    user: dict[str, Any],
    *,
    purpose: str = "verification",
) -> str:
    """Generate, store, and email an OTP. Returns the OTP (for tests/dev).

    ``purpose`` only affects the email wording ("verification" vs "login").
    """
    settings = get_settings()
    user_id = str(user.get("_id") or user.get("id"))

    # One active OTP per user — clear any previous ones.
    await database[EMAIL_OTPS_COLLECTION].delete_many({"user_id": user_id})

    otp = generate_otp(settings.otp_length)
    now = datetime.now(UTC)
    await database[EMAIL_OTPS_COLLECTION].insert_one(
        {
            "user_id": user_id,
            "otp_hash": hash_otp(otp),
            "attempts": 0,
            "expires_at": now + timedelta(minutes=settings.otp_expiry_minutes),
            "created_at": now,
        }
    )

    label = "login code" if purpose == "login" else "email verification code"
    email = user.get("email")
    if email:
        await send_email(
            database=database,
            to_email=str(email),
            subject=f"Sajilo Loan — your {label}",
            body=(
                f"Your Sajilo Loan {label} is {otp}. "
                f"It expires in {settings.otp_expiry_minutes} minutes."
            ),
        )
    return otp


async def verify_email_otp(
    database: AsyncIOMotorDatabase,
    user_id: str,
    otp: str,
) -> None:
    """Verify a submitted OTP. Raises OTPError on any failure."""
    settings = get_settings()
    record = await database[EMAIL_OTPS_COLLECTION].find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    if record is None:
        raise OTPError("No code was requested. Please try again.")

    if record.get("expires_at") and record["expires_at"] < datetime.now(UTC):
        await database[EMAIL_OTPS_COLLECTION].delete_many({"user_id": user_id})
        raise OTPError("Your code has expired. Please request a new one.")

    if int(record.get("attempts", 0)) >= settings.otp_max_attempts:
        await database[EMAIL_OTPS_COLLECTION].delete_many({"user_id": user_id})
        raise OTPError("Too many incorrect attempts. Please request a new code.")

    if not verify_otp(otp, str(record.get("otp_hash", ""))):
        await database[EMAIL_OTPS_COLLECTION].update_one(
            {"_id": record["_id"]},
            {"$set": {"attempts": int(record.get("attempts", 0)) + 1}},
        )
        raise OTPError("Incorrect code.")

    # Success — consume the OTP.
    await database[EMAIL_OTPS_COLLECTION].delete_many({"user_id": user_id})
