"""Deposit (CASA) account service — the customer's money account.

Disbursement proceeds are credited here and EMIs are auto-debited from here in
later features. This slice covers opening, reading, balance, and the CASA
lifecycle (active / dormant / closed).
"""

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.cbs.models import (
    AccountType,
    DepositAccountStatus,
    create_deposit_account_document,
    strip_id,
)
from app.cbs.services.cif import cif_exists
from app.cbs.services.sequences import next_sequence
from app.config import get_settings

DEPOSIT_COLLECTION = "cbs_deposit_accounts"


class CifRequiredError(Exception):
    """A deposit account must belong to an existing CIF."""


class DepositAccountNotFoundError(Exception):
    pass


class DepositAccountStateError(Exception):
    """The account is not in a state that allows this operation."""


def serialize_deposit_account(document: dict[str, Any]) -> dict[str, Any]:
    return strip_id(document)


def _type_code(account_type: str) -> str:
    return "01" if account_type == AccountType.SAVINGS.value else "02"


async def open_deposit_account(
    database: AsyncIOMotorDatabase,
    *,
    cif_no: str,
    account_type: str,
) -> dict[str, Any]:
    """Open a CASA account for an existing customer."""
    if not await cif_exists(database, cif_no):
        raise CifRequiredError

    settings = get_settings()
    sequence = await next_sequence(database, "deposit")
    account_no = f"{settings.cbs_branch_code}{_type_code(account_type)}{sequence:08d}"
    document = create_deposit_account_document(
        account_no=account_no,
        cif_no=cif_no,
        account_type=account_type,
        currency=settings.cbs_currency,
    )
    await database[DEPOSIT_COLLECTION].insert_one(document)
    return document


async def get_deposit_account(
    database: AsyncIOMotorDatabase,
    account_no: str,
) -> dict[str, Any]:
    document = await database[DEPOSIT_COLLECTION].find_one({"account_no": account_no})
    if document is None:
        raise DepositAccountNotFoundError
    return document


async def list_accounts_for_cif(
    database: AsyncIOMotorDatabase,
    cif_no: str,
) -> list[dict[str, Any]]:
    cursor = database[DEPOSIT_COLLECTION].find({"cif_no": cif_no}).sort("opened_at", -1)
    return [document async for document in cursor]


async def set_account_status(
    database: AsyncIOMotorDatabase,
    account_no: str,
    status: DepositAccountStatus,
) -> dict[str, Any]:
    """Move the CASA through its lifecycle (active / dormant / closed).

    A non-zero balance cannot be closed — the money must be settled first.
    """
    account = await get_deposit_account(database, account_no)
    if status == DepositAccountStatus.CLOSED and float(account.get("balance") or 0) != 0:
        raise DepositAccountStateError

    updated = await database[DEPOSIT_COLLECTION].find_one_and_update(
        {"account_no": account_no},
        {"$set": {"status": status.value, "updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise DepositAccountNotFoundError
    return updated
