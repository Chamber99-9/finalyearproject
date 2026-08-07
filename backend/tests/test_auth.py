from .conftest import get_latest_otp


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


def test_register_login_and_current_user(client, fake_database):
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
    registered_user = register_response.json()
    assert registered_user["email"] == "sita@gmail.com"
    assert registered_user["role"] == "customer"
    assert registered_user["is_email_verified"] is False
    assert "password_hash" not in registered_user

    # A brand-new account is unverified: login is challenged with an emailed
    # code instead of returning a token straight away.
    login_response = client.post(
        "/auth/login",
        json={"email": "sita@gmail.com", "password": "StrongPass1!"},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["verification_required"] is True
    assert login_body["email"] == "sita@gmail.com"
    assert not login_body.get("access_token")

    otp = get_latest_otp(fake_database, "sita@gmail.com")
    verify_response = client.post(
        "/auth/verify-otp",
        json={"email": "sita@gmail.com", "otp": otp},
    )
    assert verify_response.status_code == 200
    verify_body = verify_response.json()
    assert verify_body["token_type"] == "bearer"
    assert verify_body["access_token"]
    assert verify_body["user"]["is_email_verified"] is True

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {verify_body['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["id"] == registered_user["id"]

    # The account stays verified on subsequent logins — no further code needed.
    second_login = client.post(
        "/auth/login",
        json={"email": "sita@gmail.com", "password": "StrongPass1!"},
    )
    assert second_login.status_code == 200
    assert second_login.json()["access_token"]


def test_loan_request_blocked_until_kyc_verified(client, fake_database):
    # A newly registered customer has no KYC yet, so loan requests are blocked.
    client.post(
        "/auth/register",
        json={
            "full_name": "Gita Rai",
            "email": "gita@gmail.com",
            "phone": "9800000300",
            "password": "StrongPass1!",
        },
    )
    client.post(
        "/auth/login",
        json={"email": "gita@gmail.com", "password": "StrongPass1!"},
    )
    otp = get_latest_otp(fake_database, "gita@gmail.com")
    verify = client.post(
        "/auth/verify-otp",
        json={"email": "gita@gmail.com", "otp": otp},
    )
    token = verify.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked = client.post(
        "/applications/draft",
        json={"loan_type": "personal"},
        headers=headers,
    )
    assert blocked.status_code == 403
