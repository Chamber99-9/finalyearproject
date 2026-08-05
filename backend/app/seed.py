"""Seed demo accounts (admin / officer / customer) for local testing.

Run after the stack is up:

    docker compose run --rm seed
    # or, against any MongoDB:
    MONGODB_URI=... python -m app.seed

Logins created (change the passwords for anything real):
    admin@sajilo.test    / Admin@1234
    officer@sajilo.test  / Officer@1234
    customer@sajilo.test / Customer@1234
"""

import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

from app.auth.security import hash_password
from app.config import get_settings
from app.models.user import UserRole, create_user_document

DEMO_USERS = [
    ("admin@sajilo.test", "Admin@1234", UserRole.ADMIN, "Demo Admin", "9800000001"),
    ("officer@sajilo.test", "Officer@1234", UserRole.OFFICER, "Demo Officer", "9800000002"),
    ("customer@sajilo.test", "Customer@1234", UserRole.CUSTOMER, "Demo Customer", "9800000003"),
]


async def _wait_for_db(database, attempts: int = 30) -> None:
    for attempt in range(attempts):
        try:
            await database.command("ping")
            return
        except Exception:  # noqa: BLE001 - waiting for Mongo to accept connections
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(1)


async def seed() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    database = client[settings.mongodb_db]
    await _wait_for_db(database)

    # Ensure database indexes exist (unique email, payment refs, hot lookups).
    from app.database.indexes import ensure_indexes

    await ensure_indexes(database)

    for email, password, role, name, phone in DEMO_USERS:
        document = create_user_document(
            full_name=name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
        )
        # The demo customer is pre-KYC-verified so the loan flow is usable out
        # of the box.
        if role == UserRole.CUSTOMER:
            document["kyc_status"] = "verified"
        existing = await database["users"].find_one({"email": email})
        if existing is not None:
            updates = {
                "password_hash": document["password_hash"],
                "role": role.value,
                "is_blacklisted": False,
            }
            if role == UserRole.CUSTOMER:
                updates["kyc_status"] = "verified"
            await database["users"].update_one({"_id": existing["_id"]}, {"$set": updates})
            print(f"updated {role.value}: {email}")
        else:
            await database["users"].insert_one(document)
            print(f"created {role.value}: {email}")

        # Keep the demo customer's KYC record consistent with their verified
        # status so the dashboard KYC panel shows "verified", not a blank form.
        if role == UserRole.CUSTOMER:
            saved = await database["users"].find_one({"email": email})
            if saved is not None:
                await database["kyc_records"].update_one(
                    {"user_id": str(saved["_id"])},
                    {
                        "$set": {
                            "user_id": str(saved["_id"]),
                            "full_name": name,
                            "pan_number": "123456789",
                            "citizenship_number": "12-01-75-04321",
                            "date_of_birth": "1995-01-01",
                            "status": "verified",
                            "checks": {},
                            "review_note": "Seeded demo KYC",
                        }
                    },
                    upsert=True,
                )

    print(
        "\nDemo logins ready:\n"
        "  admin@sajilo.test    / Admin@1234\n"
        "  officer@sajilo.test  / Officer@1234\n"
        "  customer@sajilo.test / Customer@1234"
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
