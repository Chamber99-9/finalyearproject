"""Database index definitions, created at startup / during seeding.

Closes the "no indexes" gap from the architecture review: hot lookups (by
applicant, email, gateway reference, etc.) are indexed, and email/payment
references are made unique at the database level rather than relying only on
application-code checks. All calls are best-effort and idempotent — creating an
index that already exists is a no-op.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

# (collection, keys, unique)
_INDEXES: list[tuple[str, str, bool]] = [
    ("users", "email", True),
    ("users", "phone", False),
    ("payments", "provider_ref", True),
    ("payments", "applicant_id", False),
    ("payments", "loan_id", False),
    ("loan_accounts", "applicant_id", False),
    ("loan_accounts", "status", False),
    ("loan_accounts", "next_due_date", False),
    ("loan_applications", "applicant_id", False),
    ("loan_applications", "status", False),
    ("application_documents", "application_id", False),
    ("ocr_results", "document_id", False),
    ("kyc_records", "user_id", True),
    # CBS (Core Banking Simulator) — separate bounded context.
    ("cbs_cif", "cif_no", True),
    ("cbs_cif", "los_user_id", True),
    ("cbs_deposit_accounts", "account_no", True),
    ("cbs_deposit_accounts", "cif_no", False),
    ("cbs_loan_accounts", "loan_account_no", True),
    ("cbs_loan_accounts", "los_application_id", True),
    ("cbs_loan_accounts", "cif_no", False),
]


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    for collection, key, unique in _INDEXES:
        try:
            await database[collection].create_index(key, unique=unique)
        except Exception:  # noqa: BLE001 - never let index creation block startup
            continue
