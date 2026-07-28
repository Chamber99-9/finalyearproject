from app.services.loan_rate_service import get_type_spread, tenure_adjustment

from .conftest import auth_headers_for_user, seed_user
from app.models.user import UserRole


def _customer(fake_database, email, phone):
    return seed_user(fake_database, role=UserRole.CUSTOMER, email=email, phone=phone)


def test_tenure_adjustment_and_spread_pure():
    assert tenure_adjustment(120) == 1.0  # 10 years * 0.1
    assert tenure_adjustment(240) == 2.0  # capped at 2.0
    assert get_type_spread("home") == 1.0
    assert get_type_spread("instant") == 6.0


def test_quote_rate_grows_with_tenure(client, fake_database):
    headers = auth_headers_for_user(_customer(fake_database, "rate1@ex.com", "9800002001"))
    r20 = client.post(
        "/loan-rates/quote",
        headers=headers,
        json={"loan_type": "home", "tenure": 20, "tenure_unit": "years"},
    )
    r10 = client.post(
        "/loan-rates/quote",
        headers=headers,
        json={"loan_type": "home", "tenure": 10, "tenure_unit": "years"},
    )
    assert r20.status_code == 200, r20.text
    # base 8 + home 1 + tenure(20y capped 2.0) = 11.0 ; 10y => 8+1+1 = 10.0
    assert r20.json()["effective_rate"] == 11.0
    assert r10.json()["effective_rate"] == 10.0
    assert r20.json()["effective_rate"] > r10.json()["effective_rate"]


def test_instant_costs_more_than_home(client, fake_database):
    headers = auth_headers_for_user(_customer(fake_database, "rate2@ex.com", "9800002002"))
    instant = client.post(
        "/loan-rates/quote",
        headers=headers,
        json={"loan_type": "instant", "tenure": 1, "tenure_unit": "years"},
    ).json()
    home = client.post(
        "/loan-rates/quote",
        headers=headers,
        json={"loan_type": "home", "tenure": 1, "tenure_unit": "years"},
    ).json()
    assert instant["effective_rate"] > home["effective_rate"]


def test_loan_types_menu(client, fake_database):
    headers = auth_headers_for_user(_customer(fake_database, "rate3@ex.com", "9800002003"))
    response = client.get("/loan-rates/types", headers=headers)
    assert response.status_code == 200
    types = {item["loan_type"] for item in response.json()}
    assert {"personal", "instant", "home", "auto", "education", "loan_against_shares"} <= types
    instant = next(item for item in response.json() if item["loan_type"] == "instant")
    assert instant["requires_collateral_above"] is None  # instant needs no collateral


def test_preview_uses_type_and_tenure_rate(client, fake_database):
    headers = auth_headers_for_user(_customer(fake_database, "rate4@ex.com", "9800002004"))
    response = client.post(
        "/emi/preview",
        headers=headers,
        json={"loan_amount": 2000000, "tenure": 20, "tenure_unit": "years", "loan_type": "home"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["interest_rate_used"] == 11.0
    assert response.json()["monthly_emi"] > 0
