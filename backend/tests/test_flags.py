from app.models.user import UserRole

from .conftest import auth_headers_for_user, seed_application, seed_user


def test_officer_checks_suspicious_flags_and_updates_existing_result(
    client,
    fake_database,
):
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="flags.officer@example.com",
        phone="9800000400",
    )
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="flags.customer@example.com",
        phone="9800000401",
    )
    target_application = seed_application(
        fake_database,
        applicant_id=str(customer["_id"]),
        overrides={
            "citizenship_number": "DUP-100",
            "monthly_income": 10000,
            "requested_loan_amount": 250000,
        },
    )
    seed_application(
        fake_database,
        applicant_id="other-customer",
        overrides={"citizenship_number": "DUP-100"},
    )

    first_response = client.post(
        f"/flags/check/{target_application['_id']}",
        headers=auth_headers_for_user(officer),
    )
    second_response = client.post(
        f"/flags/check/{target_application['_id']}",
        headers=auth_headers_for_user(officer),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    flag_result = second_response.json()
    flag_codes = {flag["code"] for flag in flag_result["flags"]}
    assert "MISSING_REQUIRED_DOCUMENT" in flag_codes
    assert "DUPLICATE_CITIZENSHIP_NUMBER" in flag_codes
    assert "UNUSUAL_LOAN_AMOUNT" in flag_codes
    assert flag_result["total_flags"] == 3
    assert flag_result["suspicion_level"] == "High Suspicion"

    saved_count = len(
        [
            document
            for document in fake_database["application_flags"].documents
            if document["application_id"] == str(target_application["_id"])
        ]
    )
    assert saved_count == 1


def test_customer_cannot_check_suspicious_flags(client, fake_database):
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="flags.denied.customer@example.com",
        phone="9800000410",
    )
    application = seed_application(fake_database, applicant_id=str(customer["_id"]))

    response = client.post(
        f"/flags/check/{application['_id']}",
        headers=auth_headers_for_user(customer),
    )

    assert response.status_code == 403
