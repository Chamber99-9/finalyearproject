from app.models.user import UserRole
from app.services.loan_eligibility_service import (
    check_eligibility,
    max_loan_amount,
    requires_collateral,
)
from app.services.verification_service import verify_pan, verify_salary_statement

from .conftest import auth_headers_for_user, seed_user


def _customer(fake_database, email, phone):
    return seed_user(fake_database, role=UserRole.CUSTOMER, email=email, phone=phone)


def test_caps_and_collateral_pure():
    assert max_loan_amount("instant", 40000) == 20000.0  # 50% of monthly salary
    assert max_loan_amount("home", 100000) == 6000000.0  # 60x monthly income
    assert requires_collateral("home", 300000) is True
    assert requires_collateral("home", 150000) is False  # below the threshold
    assert requires_collateral("instant", 500000) is False  # instant never needs collateral


def test_pan_mock():
    assert verify_pan("123123123")["valid_format"] is True
    assert verify_pan("123123123")["tax_registered"] is True
    assert verify_pan("12ab")["valid_format"] is False
    assert verify_pan("000000000")["tax_registered"] is False  # mock defaulter


def test_salary_heuristic():
    assert verify_salary_statement(50000, 52000)["valid"] is True  # within tolerance
    assert verify_salary_statement(50000, 100000)["valid"] is False  # 50% off
    assert verify_salary_statement(0, 50000)["valid"] is False


def test_eligibility_endpoint(client, fake_database):
    headers = auth_headers_for_user(_customer(fake_database, "el1@ex.com", "9800003001"))
    response = client.post(
        "/loan-eligibility/check",
        headers=headers,
        json={"loan_type": "instant", "loan_amount": 30000, "monthly_income": 40000},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["max_amount"] == 20000.0
    assert body["within_cap"] is False  # 30000 > 20000 cap
    assert body["requires_collateral"] is False
    assert body["instant_cap"] == 20000.0


def test_pan_endpoint(client, fake_database):
    headers = auth_headers_for_user(_customer(fake_database, "el2@ex.com", "9800003002"))
    response = client.post("/verification/pan", headers=headers, json={"pan_number": "555555555"})
    assert response.status_code == 200
    assert response.json()["tax_registered"] is True


def test_submit_blocks_over_cap(client, fake_database, valid_application_payload):
    customer = seed_user(fake_database, role=UserRole.CUSTOMER, email="cap@ex.com", phone="9800003050")
    headers = auth_headers_for_user(customer)
    payload = dict(valid_application_payload)
    payload["monthly_income"] = 50000  # personal cap = 12 * 50000 = 600000
    payload["requested_loan_amount"] = 900000  # over the cap
    created = client.post("/applications", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    response = client.post(f"/applications/{created.json()['id']}/submit", headers=headers)
    assert response.status_code == 400
    assert "cap" in response.json()["detail"].lower()


def test_submit_blocks_missing_collateral(client, fake_database, valid_application_payload):
    customer = seed_user(fake_database, role=UserRole.CUSTOMER, email="coll@ex.com", phone="9800003051")
    headers = auth_headers_for_user(customer)
    payload = dict(valid_application_payload)
    payload["monthly_income"] = 200000  # cap = 2.4M, fine
    payload["requested_loan_amount"] = 900000  # > 200k personal -> needs collateral
    payload.pop("collateral_value", None)
    payload["collateral_type"] = None
    created = client.post("/applications", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    response = client.post(f"/applications/{created.json()['id']}/submit", headers=headers)
    assert response.status_code == 400
    assert "collateral" in response.json()["detail"].lower()
