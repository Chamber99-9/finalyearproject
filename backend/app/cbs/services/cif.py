"""CIF (Customer Information File) service — the CBS customer master.

One CIF per LOS user (idempotent on ``los_user_id``); deposit and loan accounts
hang off it.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.cbs.models import create_cif_document, strip_id
from app.cbs.services.sequences import next_sequence

CIF_COLLECTION = "cbs_cif"


class CifNotFoundError(Exception):
    pass


def serialize_cif(document: dict[str, Any]) -> dict[str, Any]:
    return strip_id(document)


async def create_or_get_cif(
    database: AsyncIOMotorDatabase,
    *,
    los_user_id: str,
    full_name: str,
    citizenship_no: str | None = None,
    pan: str | None = None,
    phone: str | None = None,
    kyc_status: str = "not_started",
) -> dict[str, Any]:
    """Create a CIF for an LOS user, or return the existing one (idempotent)."""
    existing = await database[CIF_COLLECTION].find_one({"los_user_id": los_user_id})
    if existing is not None:
        return existing

    sequence = await next_sequence(database, "cif")
    cif_no = f"CIF{sequence:08d}"
    document = create_cif_document(
        cif_no=cif_no,
        los_user_id=los_user_id,
        full_name=full_name,
        citizenship_no=citizenship_no,
        pan=pan,
        phone=phone,
        kyc_status=kyc_status,
    )
    await database[CIF_COLLECTION].insert_one(document)
    return document


async def get_cif(database: AsyncIOMotorDatabase, cif_no: str) -> dict[str, Any]:
    document = await database[CIF_COLLECTION].find_one({"cif_no": cif_no})
    if document is None:
        raise CifNotFoundError
    return document


async def cif_exists(database: AsyncIOMotorDatabase, cif_no: str) -> bool:
    return await database[CIF_COLLECTION].find_one({"cif_no": cif_no}) is not None
