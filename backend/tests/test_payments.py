import asyncio

from app.models.user import UserRole
from app.services.loan_account_service import create_loan_account_for_application, record_payment
from app.services.payment_service import (
    AWAITING_CONFIRMATION,
    PAYMENTS_COLLECTION,
    REJECTED,
    SUCCESS,
    confirm_payment,
    mark_payment_submitted,
    reject_payment,
)

from .conftest import auth_headers_for_user, seed_application, seed_user


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _customer(fake_database, index):
    return seed_user(
        fake_database, role=UserRole.CUSTOMER, email=f"pay{index}@ex.com", phone=f"98000050{index}"
    )


def _officer(fake_database, index):
    return seed_user(
        fake_database, role=UserRole.OFFICER, email=f"officer{index}@ex.com", phone=f"98000060{index}"
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
    return _run(create_loan_account_for_application(fake_database, application))


def _seed_payment(fake_database, *, loan_id, applicant_id, amount=44000):
    from datetime import UTC, datetime
    from uuid import uuid4

    document = {
        "loan_id": str(loan_id),
        "applicant_id": applicant_id,
        "amount": amount,
        "kind": "emi",
        "status": "pending",
        "provider": "esewa_qr",
        "provider_ref": uuid4().hex,
        "idempotency_key": uuid4().hex,
        "amount_paid": None,
        "settled_at": None,
        "checkout_url": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    return fake_database.seed(PAYMENTS_COLLECTION, document)


# ---------------------------------------------------------------------------
# Service-level: partial vs full EMI cutting based on the verified amount
# ---------------------------------------------------------------------------


def test_verified_amount_matching_emi_advances_installment(fake_database):
    customer = _customer(fake_database, 1)
    loan = _seed_loan(fake_database, str(customer["_id"]))
    before_due = loan["next_due_date"]

    updated = _run(
        record_payment(fake_database, loan["_id"], str(customer["_id"]), verified_amount=44000)
    )

    assert updated["_last_payment"] == 44000
    assert updated["_is_partial"] is False
    assert updated["installments_paid"] == 1
    assert updated["outstanding_balance"] == 484000
    assert updated["next_due_date"] != before_due


def test_verified_amount_short_of_emi_is_partial_and_does_not_advance(fake_database):
    customer = _customer(fake_database, 2)
    loan = _seed_loan(fake_database, str(customer["_id"]))
    before_due = loan["next_due_date"]

    updated = _run(
        record_payment(fake_database, loan["_id"], str(customer["_id"]), verified_amount=20000)
    )

    assert updated["_last_payment"] == 20000
    assert updated["_is_partial"] is True
    assert updated["_shortfall"] == 24000
    # No installment credited and the due date does not roll forward.
    assert updated["installments_paid"] == 0
    assert updated["outstanding_balance"] == 508000
    assert updated["next_due_date"] == before_due


def test_verified_amount_above_emi_still_counts_one_installment(fake_database):
    customer = _customer(fake_database, 3)
    loan = _seed_loan(fake_database, str(customer["_id"]))

    updated = _run(
        record_payment(fake_database, loan["_id"], str(customer["_id"]), verified_amount=60000)
    )

    assert updated["_is_partial"] is False
    assert updated["installments_paid"] == 1
    assert updated["outstanding_balance"] == 468000  # extra reduces principal further


# ---------------------------------------------------------------------------
# Service-level: submit receipt -> officer confirms/rejects
# ---------------------------------------------------------------------------


def test_confirm_uses_customer_declared_amount_when_officer_does_not_override(fake_database):
    customer = _customer(fake_database, 4)
    loan = _seed_loan(fake_database, str(customer["_id"]))
    payment = _seed_payment(fake_database, loan_id=loan["_id"], applicant_id=str(customer["_id"]))

    submitted = _run(
        mark_payment_submitted(
            fake_database,
            str(payment["_id"]),
            str(customer["_id"]),
            depositor_account_number="0123456789",
            amount_deposited=44000,
            remarks="Paid via eSewa",
        )
    )
    assert submitted["status"] == AWAITING_CONFIRMATION
    assert submitted["depositor_account_number"] == "0123456789"

    confirmed = _run(confirm_payment(fake_database, str(payment["_id"]), officer_id="off-1"))
    assert confirmed["status"] == SUCCESS
    assert confirmed["verified_amount"] == 44000
    assert confirmed["is_partial"] is False
    assert confirmed["confirmed_by"] == "off-1"


def test_officer_override_below_declared_amount_applies_partial(fake_database):
    customer = _customer(fake_database, 5)
    loan = _seed_loan(fake_database, str(customer["_id"]))
    payment = _seed_payment(fake_database, loan_id=loan["_id"], applicant_id=str(customer["_id"]))

    _run(
        mark_payment_submitted(
            fake_database,
            str(payment["_id"]),
            str(customer["_id"]),
            depositor_account_number="0123456789",
            amount_deposited=44000,
        )
    )
    # The officer checks the bank statement and only finds NPR 15,000 deposited.
    confirmed = _run(
        confirm_payment(
            fake_database,
            str(payment["_id"]),
            officer_id="off-1",
            verified_amount=15000,
            notes="Only partial deposit found on statement",
        )
    )
    assert confirmed["verified_amount"] == 15000
    assert confirmed["is_partial"] is True
    assert confirmed["shortfall"] == 29000
    assert confirmed["officer_notes"] == "Only partial deposit found on statement"


def test_reject_leaves_loan_untouched_and_customer_can_resubmit(fake_database):
    customer = _customer(fake_database, 6)
    loan = _seed_loan(fake_database, str(customer["_id"]))
    payment = _seed_payment(fake_database, loan_id=loan["_id"], applicant_id=str(customer["_id"]))

    _run(
        mark_payment_submitted(
            fake_database,
            str(payment["_id"]),
            str(customer["_id"]),
            depositor_account_number="9999999999",
            amount_deposited=44000,
        )
    )
    rejected = _run(
        reject_payment(
            fake_database,
            str(payment["_id"]),
            officer_id="off-1",
            reason="Account number does not match any deposit on the statement.",
        )
    )
    assert rejected["status"] == REJECTED

    # Customer resubmits with the correct account number.
    resubmitted = _run(
        mark_payment_submitted(
            fake_database,
            str(payment["_id"]),
            str(customer["_id"]),
            depositor_account_number="0123456789",
            amount_deposited=44000,
        )
    )
    assert resubmitted["status"] == AWAITING_CONFIRMATION


# ---------------------------------------------------------------------------
# HTTP: officer confirmation queue + review endpoints end to end
# ---------------------------------------------------------------------------


def test_officer_confirm_route_settles_and_notifies(client, fake_database):
    customer = _customer(fake_database, 7)
    officer = _officer(fake_database, 1)
    customer_headers = auth_headers_for_user(customer)
    officer_headers = auth_headers_for_user(officer)

    loan = _seed_loan(fake_database, str(customer["_id"]))
    payment = _seed_payment(fake_database, loan_id=loan["_id"], applicant_id=str(customer["_id"]))

    submit = client.post(
        f"/payments/{payment['_id']}/submitted",
        headers=customer_headers,
        json={
            "depositor_account_number": "0123456789",
            "amount_deposited": 44000,
            "remarks": "Paid via eSewa QR",
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == AWAITING_CONFIRMATION

    pending = client.get("/officer/payments/pending", headers=officer_headers)
    assert pending.status_code == 200
    assert any(item["id"] == str(payment["_id"]) for item in pending.json())

    confirm = client.post(
        f"/officer/payments/{payment['_id']}/confirm",
        headers=officer_headers,
        json={"verified_amount": 44000, "notes": "Matches statement line 12"},
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["status"] == SUCCESS
    assert body["installments_paid_after"] == 1
