from .conftest import get_latest_otp


def test_customer_can_create_and_list_own_application(
    client,
    fake_database,
    valid_application_payload,
):
    register_response = client.post(
        "/auth/register",
        json={
            "full_name": "Application Customer",
            "email": "application.customer@gmail.com",
            "phone": "9800000200",
            "password": "StrongPass1!",
        },
    )
    user = register_response.json()
    client.post(
        "/auth/login",
        json={
            "email": "application.customer@gmail.com",
            "password": "StrongPass1!",
        },
    )
    otp = get_latest_otp(fake_database, "application.customer@gmail.com")
    verify_response = client.post(
        "/auth/verify-otp",
        json={"email": "application.customer@gmail.com", "otp": otp},
    )
    headers = {"Authorization": f"Bearer {verify_response.json()['access_token']}"}

    create_response = client.post(
        "/applications",
        json=valid_application_payload,
        headers=headers,
    )

    assert create_response.status_code == 201
    application = create_response.json()
    assert application["applicant_id"] == user["id"]
    assert application["status"] == "draft"
    assert application["citizenship_number"] == valid_application_payload["citizenship_number"]

    list_response = client.get("/applications/my", headers=headers)

    assert list_response.status_code == 200
    applications = list_response.json()
    assert len(applications) == 1
    assert applications[0]["id"] == application["id"]
