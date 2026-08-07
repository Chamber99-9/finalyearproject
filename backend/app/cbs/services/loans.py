"""Loan account service — opens a CBS loan account from an approved LOS sanction.

The loan account is created ``PENDING_DISBURSEMENT``: the terms are booked but no
money has moved and nothing is owed yet (``principal_outstanding = 0``). The
disbursement feature (later) posts the ledger entry, funds the CASA, generates
the schedule, and flips the loan to ``ACTIVE``.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.cbs.models import create_loan_account_document, strip_id
from app.cbs.services.cif import cif_exists
from app.cbs.services.accounts import DEPOSIT_COLLECTION
from app.cbs.services.sequences import next_sequence
from app.config import get_settings

LOAN_COLLECTION = "cbs_loan_accounts"


class CifRequiredError(Exception):
    pass


class DisbursementAccountRequiredError(Exception):
    """A loan needs a valid CASA (owned by the same CIF) to disburse into."""


class LoanAccountNotFoundError(Exception):
    pass


class LoanTermsError(Exception):
    """Sanction terms are invalid (amount / tenure / rate)."""


def serialize_loan_account(document: dict[str, Any]) -> dict[str, Any]:
    return strip_id(document)


async def open_loan_account(
    database: AsyncIOMotorDatabase,
    *,
    cif_no: str,
    product_code: str,
    los_application_id: str,
    sanction_amount: float,
    interest_rate: float,
    tenure_months: int,
    emi_amount: float,
    disbursement_account_no: str,
) -> dict[str, Any]:
    """Open a loan account from an approved sanction (idempotent per application)."""
    if sanction_amount <= 0 or tenure_months <= 0 or interest_rate < 0:
        raise LoanTermsError

    if not await cif_exists(database, cif_no):
        raise CifRequiredError

    casa = await database[DEPOSIT_COLLECTION].find_one(
        {"account_no": disbursement_account_no, "cif_no": cif_no}
    )
    if casa is None:
        raise DisbursementAccountRequiredError

    # One loan account per LOS application (idempotent) — retries never duplicate.
    existing = await database[LOAN_COLLECTION].find_one(
        {"los_application_id": los_application_id}
    )
    if existing is not None:
        return existing

    settings = get_settings()
    sequence = await next_sequence(database, "loan")
    loan_account_no = f"{settings.cbs_branch_code}LN{sequence:08d}"
    document = create_loan_account_document(
        loan_account_no=loan_account_no,
        cif_no=cif_no,
        product_code=product_code,
        los_application_id=los_application_id,
        sanction_amount=sanction_amount,
        interest_rate=interest_rate,
        tenure_months=tenure_months,
        emi_amount=emi_amount,
        disbursement_account_no=disbursement_account_no,
        currency=settings.cbs_currency,
    )
    await database[LOAN_COLLECTION].insert_one(document)
    return document


async def get_loan_account(
    database: AsyncIOMotorDatabase,
    loan_account_no: str,
) -> dict[str, Any]:
    document = await database[LOAN_COLLECTION].find_one({"loan_account_no": loan_account_no})
    if document is None:
        raise LoanAccountNotFoundError
    return document


async def list_loans_for_cif(
    database: AsyncIOMotorDatabase,
    cif_no: str,
) -> list[dict[str, Any]]:
    cursor = database[LOAN_COLLECTION].find({"cif_no": cif_no}).sort("created_at", -1)
    return [document async for document in cursor]
