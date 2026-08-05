import pytest

from app.services import otp_service

FIXED_OTP = "123456"


@pytest.fixture(autouse=True)
def fixed_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make the emailed OTP deterministic so the verification flow is testable.
    monkeypatch.setattr(otp_service, "generate_otp", lambda *_a, **_k: FIXED_OTP)


def test_registration_requires_gmail(client):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Sita Sharma",
            "email": "sita@example.com",
            "phone": "9800000100",
            "password": "StrongPass1!",
        },
    )
    # Non-Gmail addresses are rejected by validation.
    assert response.status_code == 422


def test_register_verify_and_current_user(client):
    register_response = client.post(
        "/auth/register",
        json={
            "full_name": "Sita Sharma",
            "email": "sita@gmail.com",
            "phone": "9800000100",
            "password": "StrongPass1!",
        },
    )
    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["verification_required"] is True
    assert register_body["email"] == "sita@gmail.com"

    # Login before verification returns a verification challenge, not a token.
    unverified_login = client.post(
        "/auth/login",
        json={"email": "sita@gmail.com", "password": "StrongPass1!"},
    )
    assert unverified_login.status_code == 200
    assert unverified_login.json().get("verification_required") is True
    assert not unverified_login.json().get("access_token")

    # Verifying the emailed OTP activates the account and issues a token.
    verify_response = client.post(
        "/auth/verify-otp",
        json={"email": "sita@gmail.com", "otp": FIXED_OTP},
    )
    assert verify_response.status_code == 200
    verify_body = verify_response.json()
    token = verify_body["access_token"]
    assert token
    assert verify_body["user"]["email_verified"] is True

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "sita@gmail.com"

    # After verification, a normal login issues a token directly.
    verified_login = client.post(
        "/auth/login",
        json={"email": "sita@gmail.com", "password": "StrongPass1!"},
    )
    assert verified_login.status_code == 200
    assert verified_login.json()["access_token"]


def test_loan_request_blocked_until_kyc_verified(client):
    # A freshly registered + email-verified customer still has no KYC.
    client.post(
        "/auth/register",
        json={
            "full_name": "Gita Rai",
            "email": "gita@gmail.com",
            "phone": "9800000300",
            "password": "StrongPass1!",
        },
    )
    verify = client.post(
        "/auth/verify-otp",
        json={"email": "gita@gmail.com", "otp": FIXED_OTP},
    )
    token = verify.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked = client.post(
        "/applications/draft",
        json={"loan_type": "personal"},
        headers=headers,
    )
    assert blocked.status_code == 403


def test_wrong_otp_is_rejected(client):
    client.post(
        "/auth/register",
        json={
            "full_name": "Hari Thapa",
            "email": "hari@gmail.com",
            "phone": "9800000200",
            "password": "StrongPass1!",
        },
    )
    response = client.post(
        "/auth/verify-otp",
        json={"email": "hari@gmail.com", "otp": "000000"},
    )
    assert response.status_code == 401
