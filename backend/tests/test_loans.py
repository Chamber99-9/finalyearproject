import asyncio
from datetime import UTC, datetime, timedelta

from app.auth.security import hash_password
from app.models.user import UserRole, create_user_document
from app.services.loan_account_service import create_loan_account_for_application

from .conftest import auth_headers_for_user, seed_application, seed_user


def _customer(fake_database, index):
    return seed_user(
        fake_database, role=UserRole.CUSTOMER, email=f"ln{index}@ex.com", phone=f"98000040{index}"
    )


def _seed_loan(fake_database, applicant_id, **overrides):
    application = seed_application(
        fake_database,
        applicant_id=applicant_id,
        overrides={
            "requested_loan_amount": 500000,
            "loan_duration_months": 12,
            "monthly_emi": 44000,
            "total_payment": 528000,
            "total_interest": 28000,
            "interest_rate_used": 11,
            **overrides,
        },
    )
    return asyncio.get_event_loop().run_until_complete(
        create_loan_account_for_application(fake_database, application)
    )


def test_payment_reduces_balance(client, fake_database):
    customer = _customer(fake_database, 1)
    headers = auth_headers_for_user(customer)
    loan = _seed_loan(fake_database, str(customer["_id"]))
    before = client.get("/loans/my", headers=headers).json()[0]["outstanding_balance"]
    response = client.post(f"/loans/{loan['_id']}/pay", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["amount_paid"] == 44000
    assert body["loan"]["outstanding_balance"] == round(before - 44000, 2)
    assert body["loan"]["installments_paid"] == 1


def test_blacklist_blocks_login(client, fake_database):
    document = create_user_document(
        full_name="Bad Payer",
        email="black@ex.com",
        phone="9800004099",
        password_hash=hash_password("StrongPass1!"),
        role=UserRole.CUSTOMER,
    )
    document["is_blacklisted"] = True
    fake_database.seed("users", document)
    response = client.post("/auth/login", json={"email": "black@ex.com", "password": "StrongPass1!"})
    assert response.status_code == 403
    assert "blacklist" in response.json()["detail"].lower()


def test_overdue_blacklists_after_threshold(client, fake_database):
    admin = seed_user(fake_database, role=UserRole.ADMIN, email="lnadmin@ex.com", phone="9800004050")
    customer = _customer(fake_database, 2)
    _seed_loan(fake_database, str(customer["_id"]))
    fake_database["loan_accounts"].documents[0]["next_due_date"] = datetime.now(UTC) - timedelta(days=5)
    fake_database["loan_accounts"].documents[0]["missed_installments"] = 2  # threshold 3
    response = client.post("/loans/maintenance/overdue", headers=auth_headers_for_user(admin))
    assert response.status_code == 200, response.text
    assert response.json()["blacklisted"] == 1
    login = client.post("/auth/login", json={"email": "ln2@ex.com", "password": "StrongPass1!"})
    assert login.status_code == 403


def test_reminders_run_and_store_email(client, fake_database):
    admin = seed_user(fake_database, role=UserRole.ADMIN, email="rem@ex.com", phone="9800004060")
    customer = _customer(fake_database, 3)
    _seed_loan(fake_database, str(customer["_id"]))
    fake_database["loan_accounts"].documents[0]["next_due_date"] = datetime.now(UTC) + timedelta(days=1)
    response = client.post("/loans/maintenance/reminders", headers=auth_headers_for_user(admin))
    assert response.status_code == 200, response.text
    assert response.json()["reminded"] == 1
    assert len(fake_database["emails"].documents) == 1


def test_approved_application_opens_loan(client, fake_database):
    officer = seed_user(fake_database, role=UserRole.OFFICER, email="lnoff@ex.com", phone="9800004070")
    customer = _customer(fake_database, 4)
    application = seed_application(
        fake_database,
        applicant_id=str(customer["_id"]),
        overrides={
            "monthly_emi": 44000,
            "total_payment": 528000,
            "total_interest": 28000,
            "loan_duration_months": 12,
            "requested_loan_amount": 500000,
            "interest_rate_used": 11,
        },
    )
    response = client.put(
        f"/officer/applications/{application['_id']}/status",
        headers=auth_headers_for_user(officer),
        json={"status": "approved", "note": "ok"},
    )
    assert response.status_code == 200, response.text
    loans = client.get("/loans/my", headers=auth_headers_for_user(customer)).json()
    assert len(loans) == 1
    assert loans[0]["status"] == "active"
