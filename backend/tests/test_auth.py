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


def test_register_login_and_current_user(client):
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
    assert "password_hash" not in registered_user

    login_response = client.post(
        "/auth/login",
        json={"email": "sita@gmail.com", "password": "StrongPass1!"},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["token_type"] == "bearer"
    assert login_body["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_body['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["id"] == registered_user["id"]


def test_loan_request_blocked_until_kyc_verified(client):
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
    login = client.post(
        "/auth/login",
        json={"email": "gita@gmail.com", "password": "StrongPass1!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked = client.post(
        "/applications/draft",
        json={"loan_type": "personal"},
        headers=headers,
    )
    assert blocked.status_code == 403
