"""CBS Customer Account + Loan Account module tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models.user import UserRole
from tests.conftest import FakeDatabase, auth_headers_for_user, seed_user


@pytest.fixture
def officer_headers(fake_database: FakeDatabase) -> dict[str, str]:
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="officer.cbs@example.com",
        phone="9811111111",
    )
    return auth_headers_for_user(officer)


def _create_cif(client: TestClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    payload = {
        "los_user_id": "user-1",
        "full_name": "Sita Sharma",
        "citizenship_no": "12-34-56-78901",
        "phone": "9800000000",
    }
    payload.update(overrides)
    response = client.post("/cbs/v1/cif", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_cif_creation_is_idempotent(client: TestClient, officer_headers: dict[str, str]) -> None:
    first = _create_cif(client, officer_headers)
    second = _create_cif(client, officer_headers)
    assert first["cif_no"] == second["cif_no"]
    assert first["cif_no"].startswith("CIF")


def test_requires_authentication(client: TestClient) -> None:
    response = client.post("/cbs/v1/cif", json={"los_user_id": "x", "full_name": "No Auth"})
    assert response.status_code in (401, 403)


def test_open_deposit_account_and_balance(
    client: TestClient, officer_headers: dict[str, str]
) -> None:
    cif = _create_cif(client, officer_headers)

    response = client.post(
        "/cbs/v1/deposit-accounts",
        json={"cif_no": cif["cif_no"], "account_type": "savings"},
        headers=officer_headers,
    )
    assert response.status_code == 201, response.text
    account = response.json()
    assert account["balance"] == 0.0
    assert account["status"] == "active"
    assert account["account_no"].startswith("001" + "01")

    balance = client.get(
        f"/cbs/v1/deposit-accounts/{account['account_no']}/balance",
        headers=officer_headers,
    )
    assert balance.status_code == 200
    assert balance.json()["balance"] == 0.0


def test_deposit_account_requires_existing_cif(
    client: TestClient, officer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/cbs/v1/deposit-accounts",
        json={"cif_no": "CIF99999999", "account_type": "savings"},
        headers=officer_headers,
    )
    assert response.status_code == 404


def test_open_loan_account(client: TestClient, officer_headers: dict[str, str]) -> None:
    cif = _create_cif(client, officer_headers)
    casa = client.post(
        "/cbs/v1/deposit-accounts",
        json={"cif_no": cif["cif_no"], "account_type": "savings"},
        headers=officer_headers,
    ).json()

    loan_payload = {
        "cif_no": cif["cif_no"],
        "product_code": "PERSONAL",
        "los_application_id": "app-1",
        "sanction_amount": 500000,
        "interest_rate": 12.5,
        "tenure_months": 24,
        "emi_amount": 23570.5,
        "disbursement_account_no": casa["account_no"],
    }
    response = client.post("/cbs/v1/loans", json=loan_payload, headers=officer_headers)
    assert response.status_code == 201, response.text
    loan = response.json()
    assert loan["status"] == "pending_disbursement"
    assert loan["principal_outstanding"] == 0.0
    assert loan["installments_total"] == 24
    assert loan["loan_account_no"].startswith("001LN")

    # Idempotent per LOS application.
    again = client.post("/cbs/v1/loans", json=loan_payload, headers=officer_headers)
    assert again.status_code == 201
    assert again.json()["loan_account_no"] == loan["loan_account_no"]


def test_loan_rejects_unknown_disbursement_account(
    client: TestClient, officer_headers: dict[str, str]
) -> None:
    cif = _create_cif(client, officer_headers)
    response = client.post(
        "/cbs/v1/loans",
        json={
            "cif_no": cif["cif_no"],
            "product_code": "PERSONAL",
            "los_application_id": "app-2",
            "sanction_amount": 100000,
            "interest_rate": 10,
            "tenure_months": 12,
            "emi_amount": 8791.6,
            "disbursement_account_no": "00101999",
        },
        headers=officer_headers,
    )
    assert response.status_code == 422


def test_closing_account_with_balance_conflicts(
    client: TestClient, officer_headers: dict[str, str], fake_database: FakeDatabase
) -> None:
    cif = _create_cif(client, officer_headers)
    account = client.post(
        "/cbs/v1/deposit-accounts",
        json={"cif_no": cif["cif_no"], "account_type": "current"},
        headers=officer_headers,
    ).json()

    # Simulate a funded account.
    for document in fake_database["cbs_deposit_accounts"].documents:
        if document["account_no"] == account["account_no"]:
            document["balance"] = 5000.0

    response = client.patch(
        f"/cbs/v1/deposit-accounts/{account['account_no']}/status",
        json={"status": "closed"},
        headers=officer_headers,
    )
    assert response.status_code == 409
