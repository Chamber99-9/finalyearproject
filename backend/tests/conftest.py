from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.database import get_database
from app.main import app
from app.models.user import UserRole, create_user_document


class FakeInsertOneResult:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, key: str, direction: int) -> "FakeCursor":
        reverse = direction == -1
        self._documents.sort(key=lambda document: document.get(key), reverse=reverse)
        return self

    def __aiter__(self) -> "FakeCursor":
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._index >= len(self._documents):
            raise StopAsyncIteration
        document = self._documents[self._index]
        self._index += 1
        return deepcopy(document)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    async def insert_one(self, document: dict[str, Any]) -> FakeInsertOneResult:
        stored_document = deepcopy(document)
        inserted_id = stored_document.get("_id")
        if not isinstance(inserted_id, ObjectId):
            inserted_id = ObjectId()
            stored_document["_id"] = inserted_id
        self.documents.append(stored_document)
        return FakeInsertOneResult(inserted_id)

    async def find_one(
        self,
        query: dict[str, Any],
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, Any] | None:
        matches = [document for document in self.documents if _matches(document, query)]
        if sort:
            for key, direction in reversed(sort):
                matches.sort(
                    key=lambda document: document.get(key),
                    reverse=direction == -1,
                )
        return deepcopy(matches[0]) if matches else None

    def find(self, query: dict[str, Any]) -> FakeCursor:
        return FakeCursor(
            [deepcopy(document) for document in self.documents if _matches(document, query)]
        )

    async def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
        return_document: Any = None,
    ) -> dict[str, Any] | None:
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                updated_document = deepcopy(document)
                _apply_update(updated_document, update)
                self.documents[index] = updated_document
                return deepcopy(updated_document)

        if not upsert:
            return None

        new_document: dict[str, Any] = {
            key: value for key, value in query.items() if not isinstance(value, dict)
        }
        new_document["_id"] = ObjectId()
        _apply_update(new_document, update)
        self.documents.append(deepcopy(new_document))
        return deepcopy(new_document)

    async def count_documents(self, query: dict[str, Any]) -> int:
        return sum(1 for document in self.documents if _matches(document, query))


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]

    def seed(self, collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
        stored_document = deepcopy(document)
        stored_document.setdefault("_id", ObjectId())
        self[collection_name].documents.append(stored_document)
        return deepcopy(stored_document)


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    return all(_field_matches(document.get(key), expected) for key, expected in query.items())


def _field_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        for operator, value in expected.items():
            if operator == "$ne" and actual == value:
                return False
            if operator == "$in" and actual not in value:
                return False
        return True
    return actual == expected


def _apply_update(document: dict[str, Any], update: dict[str, Any]) -> None:
    if "$set" in update:
        document.update(deepcopy(update["$set"]))
        return
    document.update(deepcopy(update))


@pytest.fixture(autouse=True)
def disable_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    def allow_request(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr("app.routes.auth.enforce_rate_limit", allow_request)
    monkeypatch.setattr("app.routes.applications.enforce_rate_limit", allow_request)
    monkeypatch.setattr("app.routes.risk.enforce_rate_limit", allow_request)
    monkeypatch.setattr("app.routes.flags.enforce_rate_limit", allow_request)


@pytest.fixture
def fake_database() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def client(fake_database: FakeDatabase) -> Iterator[TestClient]:
    app.dependency_overrides[get_database] = lambda: fake_database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def valid_application_payload() -> dict[str, Any]:
    return {
        "full_name": "Krishna Cena",
        "citizenship_number": "CTZ-1001",
        "phone": "9800000001",
        "address": "Kathmandu, Nepal",
        "loan_type": "personal",
        "monthly_income": 100000,
        "employment_type": "salaried",
        "existing_monthly_debt": 20000,
        "requested_loan_amount": 900000,
        "loan_duration_months": 24,
        "annual_interest_rate": 12,
        "loan_tenure": 24,
        "tenure_unit": "months",
        "loan_purpose": "Home improvement",
        "dependents": 1,
        "savings_buffer": "good",
        "repayment_history": "no_previous_default",
    }


def seed_user(
    fake_database: FakeDatabase,
    *,
    role: UserRole,
    email: str,
    phone: str,
    full_name: str = "Test User",
    password: str = "StrongPass1!",
) -> dict[str, Any]:
    return fake_database.seed(
        "users",
        create_user_document(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
        ),
    )


def auth_headers_for_user(user: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user['_id']))}"}


def seed_application(
    fake_database: FakeDatabase,
    *,
    applicant_id: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    document = {
        "applicant_id": applicant_id,
        "full_name": "Krishna Cena",
        "citizenship_number": "CTZ-1001",
        "phone": "9800000001",
        "address": "Kathmandu, Nepal",
        "loan_type": "personal",
        "monthly_income": 100000,
        "employment_type": "salaried",
        "existing_monthly_debt": 20000,
        "requested_loan_amount": 900000,
        "loan_duration_months": 24,
        "annual_interest_rate": 12,
        "loan_tenure": 24,
        "tenure_unit": "months",
        "loan_purpose": "Home improvement",
        "dependents": 1,
        "savings_buffer": "good",
        "repayment_history": "no_previous_default",
        "status": "submitted",
        "created_at": now,
        "updated_at": now,
    }
    if overrides:
        document.update(overrides)
    return fake_database.seed("loan_applications", document)
