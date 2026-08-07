"""Atomic, gap-free number generator for CBS account numbers.

Uses a single find_one_and_update with ``$inc`` (atomic in MongoDB), which is
how a core banking system issues sequential CIF / account numbers safely under
concurrency.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

CBS_SEQUENCES_COLLECTION = "cbs_sequences"


async def next_sequence(database: AsyncIOMotorDatabase, name: str) -> int:
    document = await database[CBS_SEQUENCES_COLLECTION].find_one_and_update(
        {"_id": name},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(document["value"])
