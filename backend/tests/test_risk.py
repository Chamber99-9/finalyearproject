from app.models.user import UserRole

from .conftest import auth_headers_for_user, seed_application, seed_user


def test_officer_can_calculate_credit_risk(
    client,
    fake_database,
):
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="risk.officer@example.com",
        phone="9800000300",
    )
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="risk.customer@example.com",
        phone="9800000301",
    )
    application = seed_application(fake_database, applicant_id=str(customer["_id"]))

    response = client.post(
        f"/risk/calculate/{application['_id']}",
        headers=auth_headers_for_user(officer),
    )

    assert response.status_code == 200
    risk_score = response.json()
    assert risk_score["application_id"] == str(application["_id"])
    assert risk_score["score_type"] == "rule_based_credit_risk_score"
    assert 0 <= risk_score["raw_score"] <= 100
    assert 300 <= risk_score["normalized_score"] <= 850
    assert risk_score["score_breakdown"]
    assert risk_score["repayment_history_used"] == "no_previous_default"
    assert risk_score["repayment_history_score"] == 20
    assert risk_score["scoring_model_version"] == "v1"
    assert "not an official credit bureau score" in risk_score["disclaimer"]
    assert risk_score["dti_ratio"] == 20
    assert risk_score["lti_ratio"] == 9


def test_admin_can_calculate_credit_risk(client, fake_database):
    admin = seed_user(
        fake_database,
        role=UserRole.ADMIN,
        email="risk.admin@example.com",
        phone="9800000310",
    )
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="risk.admin.customer@example.com",
        phone="9800000311",
    )
    application = seed_application(fake_database, applicant_id=str(customer["_id"]))

    response = client.post(
        f"/risk/calculate/{application['_id']}",
        headers=auth_headers_for_user(admin),
    )

    assert response.status_code == 200
    assert response.json()["scoring_model_version"] == "v1"


def test_customer_cannot_calculate_credit_risk(client, fake_database):
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="risk.denied.customer@example.com",
        phone="9800000320",
    )
    application = seed_application(fake_database, applicant_id=str(customer["_id"]))

    response = client.post(
        f"/risk/calculate/{application['_id']}",
        headers=auth_headers_for_user(customer),
    )

    assert response.status_code == 403


def test_credit_risk_uses_unknown_repayment_history_when_missing(
    client,
    fake_database,
):
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="risk.unknown.officer@example.com",
        phone="9800000340",
    )
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="risk.unknown.customer@example.com",
        phone="9800000341",
    )
    application = seed_application(
        fake_database,
        applicant_id=str(customer["_id"]),
        overrides={"repayment_history": None},
    )

    response = client.post(
        f"/risk/calculate/{application['_id']}",
        headers=auth_headers_for_user(officer),
    )

    assert response.status_code == 200
    risk_score = response.json()
    assert risk_score["repayment_history_used"] == "unknown"
    assert risk_score["repayment_history_score"] == 12
    assert risk_score["score_breakdown"]["repayment_history_score"] == 12
    assert 0 <= risk_score["raw_score"] <= 100
    assert 300 <= risk_score["normalized_score"] <= 850


def test_credit_risk_scores_minor_late_payment_as_ten_points(
    client,
    fake_database,
):
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="risk.late.officer@example.com",
        phone="9800000350",
    )
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="risk.late.customer@example.com",
        phone="9800000351",
    )
    application = seed_application(
        fake_database,
        applicant_id=str(customer["_id"]),
        overrides={"repayment_history": "minor_late_payment"},
    )

    response = client.post(
        f"/risk/calculate/{application['_id']}",
        headers=auth_headers_for_user(officer),
    )

    assert response.status_code == 200
    risk_score = response.json()
    assert risk_score["repayment_history_used"] == "minor_late_payment"
    assert risk_score["repayment_history_score"] == 10
    assert risk_score["score_breakdown"]["repayment_history_score"] == 10


def test_credit_risk_rejects_invalid_monthly_income(client, fake_database):
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="risk.invalid.officer@example.com",
        phone="9800000330",
    )
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="risk.invalid.customer@example.com",
        phone="9800000331",
    )
    application = seed_application(
        fake_database,
        applicant_id=str(customer["_id"]),
        overrides={"monthly_income": 0},
    )

    response = client.post(
        f"/risk/calculate/{application['_id']}",
        headers=auth_headers_for_user(officer),
    )

    assert response.status_code == 400
    assert "monthly_income" in response.json()["detail"]
