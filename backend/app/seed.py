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

    for email, password, role, name, phone in DEMO_USERS:
        document = create_user_document(
            full_name=name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
        )
        existing = await database["users"].find_one({"email": email})
        if existing is not None:
            await database["users"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "password_hash": document["password_hash"],
                        "role": role.value,
                        "is_blacklisted": False,
                    }
                },
            )
            print(f"updated {role.value}: {email}")
        else:
            await database["users"].insert_one(document)
            print(f"created {role.value}: {email}")

    print(
        "\nDemo logins ready:\n"
        "  admin@sajilo.test    / Admin@1234\n"
        "  officer@sajilo.test  / Officer@1234\n"
        "  customer@sajilo.test / Customer@1234"
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
