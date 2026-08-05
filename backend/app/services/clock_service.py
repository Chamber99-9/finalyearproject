"""Simulated application clock (for testing time-based features).

Reminders, overdue counting, blacklisting and the EMI payment window are all
driven by ``simulated_now`` rather than the wall clock. An admin can skip days
forward via a stored day-offset so features that would otherwise take a month to
fire (3-day reminders, overdue → blacklist) can be exercised immediately.

The offset lives in the ``app_settings`` collection as a single keyed document.
Offset 0 means the simulated clock equals the real clock.
"""

from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

APP_SETTINGS_COLLECTION = "app_settings"
CLOCK_OFFSET_KEY = "simulated_day_offset"


async def get_offset_days(database: AsyncIOMotorDatabase) -> int:
    document = await database[APP_SETTINGS_COLLECTION].find_one({"key": CLOCK_OFFSET_KEY})
    if document is not None and document.get("value") is not None:
        try:
            return int(document["value"])
        except (TypeError, ValueError):
            return 0
    return 0


async def simulated_now(database: AsyncIOMotorDatabase) -> datetime:
    """The current simulated time = real now + stored day offset."""
    return datetime.now(UTC) + timedelta(days=await get_offset_days(database))


async def _set_offset(database: AsyncIOMotorDatabase, days: int) -> int:
    await database[APP_SETTINGS_COLLECTION].update_one(
        {"key": CLOCK_OFFSET_KEY},
        {
            "$set": {
                "key": CLOCK_OFFSET_KEY,
                "value": int(days),
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    return int(days)


async def advance_days(database: AsyncIOMotorDatabase, days: int) -> int:
    """Skip the simulated clock forward (or back) by ``days``; returns new offset."""
    current = await get_offset_days(database)
    return await _set_offset(database, current + int(days))


async def reset_clock(database: AsyncIOMotorDatabase) -> int:
    """Reset the simulated clock back to the real clock (offset 0)."""
    return await _set_offset(database, 0)
