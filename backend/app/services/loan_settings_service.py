"""Bank-defined loan settings (currently just the Personal Loan interest rate).

The live value is stored in the ``app_settings`` collection as a single keyed
document, falling back to the config default when no override has been saved.

The read/write helpers are keyed by loan type so additional loan products can be
introduced later without any schema change — only a new key and a config default
would be needed. The project intentionally ships with Personal Loan only.
"""

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.models.application import LoanType

APP_SETTINGS_COLLECTION = "app_settings"


class LoanSettingsError(Exception):
    pass


def _interest_rate_key(loan_type: str) -> str:
    return f"loan_interest_rate:{loan_type}"


def _default_interest_rate(loan_type: str) -> float:
    # Only Personal Loan has a configured default today. Future products would
    # add their own config default here (or seed the collection).
    if loan_type == LoanType.PERSONAL.value:
        return float(get_settings().personal_loan_interest_rate)
    return float(get_settings().personal_loan_interest_rate)


async def get_loan_interest_rate(
    database: AsyncIOMotorDatabase,
    loan_type: str = LoanType.PERSONAL.value,
) -> float:
    """Return the current bank interest rate for a loan type.

    Reads the saved override from ``app_settings`` and falls back to the config
    default when none has been set.
    """
    document = await database[APP_SETTINGS_COLLECTION].find_one(
        {"key": _interest_rate_key(loan_type)}
    )
    if document is not None and document.get("value") is not None:
        try:
            return float(document["value"])
        except (TypeError, ValueError):
            pass
    return _default_interest_rate(loan_type)


async def set_loan_interest_rate(
    database: AsyncIOMotorDatabase,
    interest_rate: float,
    loan_type: str = LoanType.PERSONAL.value,
) -> float:
    """Persist a new bank interest rate override for a loan type."""
    if interest_rate <= 0:
        raise LoanSettingsError("Interest rate must be greater than 0.")

    await database[APP_SETTINGS_COLLECTION].update_one(
        {"key": _interest_rate_key(loan_type)},
        {
            "$set": {
                "key": _interest_rate_key(loan_type),
                "value": float(interest_rate),
                "loan_type": loan_type,
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    return float(interest_rate)


async def get_personal_loan_interest_rate(database: AsyncIOMotorDatabase) -> float:
    return await get_loan_interest_rate(database, LoanType.PERSONAL.value)


async def set_personal_loan_interest_rate(
    database: AsyncIOMotorDatabase,
    interest_rate: float,
) -> float:
    return await set_loan_interest_rate(database, interest_rate, LoanType.PERSONAL.value)
