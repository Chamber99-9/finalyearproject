"""Payment gateway integration pattern.

Real-world flow:
  1. Customer initiates a payment -> we create a PENDING payment intent with an
     idempotency key and a provider reference (in production this returns a
     gateway checkout URL).
  2. The gateway confirms out-of-band and calls our webhook. We verify the HMAC
     signature and settle the payment idempotently, applying it to the loan.

This module never marks a loan paid without a settled payment, and settling the
same payment twice is a no-op (idempotency) — the core guarantees a real payment
system needs.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.auth.security import sign_payload, verify_signature
from app.config import get_settings
from app.services.clock_service import simulated_now
from app.services.loan_account_service import (
    LoanAccountNotFoundError,
    LoanAccountStatusError,
    record_payment,
    record_prepayment,
)

PAYMENTS_COLLECTION = "payments"

PENDING = "pending"
SUCCESS = "success"
FAILED = "failed"

EMI_KIND = "emi"
PREPAYMENT_KIND = "prepayment"


class PaymentNotFoundError(Exception):
    pass


class PaymentSignatureError(Exception):
    pass


class PaymentWindowError(Exception):
    """EMI cannot be paid yet — outside the allowed payment window."""

    def __init__(self, payable_from: datetime) -> None:
        super().__init__("EMI is not payable yet.")
        self.payable_from = payable_from


class PrepaymentAmountError(Exception):
    """Advance amount must be between 1 and the outstanding balance."""


def serialize_payment(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document


def webhook_payload(provider_ref: str, status: str) -> str:
    """Canonical JSON body the gateway signs (used by webhook + simulator)."""
    return json.dumps({"provider_ref": provider_ref, "status": status}, sort_keys=True)


def sign_webhook(provider_ref: str, status: str) -> str:
    secret = get_settings().payment_webhook_secret
    return sign_payload(webhook_payload(provider_ref, status), secret)


async def initiate_payment(
    database: AsyncIOMotorDatabase,
    loan_id: str,
    applicant_id: str,
    *,
    return_url_base: str | None = None,
    customer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a PENDING payment intent for one EMI on an active, owned loan.

    With the mock provider, the checkout URL is our internal page. With a real
    rail (Khalti), we call the gateway's initiate API and hand back its hosted
    checkout URL for the customer to be redirected to.
    """
    if not ObjectId.is_valid(loan_id):
        raise LoanAccountNotFoundError
    loan = await database["loan_accounts"].find_one(
        {"_id": ObjectId(loan_id), "applicant_id": applicant_id}
    )
    if loan is None:
        raise LoanAccountNotFoundError
    if loan.get("status") != "active":
        raise LoanAccountStatusError

    settings = get_settings()
    now = await simulated_now(database)
    # EMI can only be paid within the window before the due date (or once overdue).
    due = loan.get("next_due_date")
    window = timedelta(days=settings.emi_payment_window_days)
    if isinstance(due, datetime) and now < (due - window):
        raise PaymentWindowError(due - window)

    amount = float(loan.get("monthly_emi") or 0)
    document = {
        "loan_id": loan_id,
        "applicant_id": applicant_id,
        "amount": amount,
        "kind": EMI_KIND,
        "status": PENDING,
        "provider": "mock_gateway",
        "provider_ref": uuid4().hex,
        "idempotency_key": uuid4().hex,
        "amount_paid": None,
        "settled_at": None,
        "checkout_url": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await database[PAYMENTS_COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    payment_id = str(document["_id"])

    if settings.payment_provider == "esewa":
        from app.services.payment_gateways import esewa_build_form

        base = return_url_base or settings.payment_return_url_base
        # eSewa uses our payment id as the transaction_uuid so the status check
        # can be correlated back to this intent.
        form = esewa_build_form(
            amount=amount,
            transaction_uuid=payment_id,
            success_url=f"{base}/payments/return",
            failure_url=f"{base}/payments/return?status=failed",
        )
        updates = {
            "provider": "esewa",
            "provider_ref": payment_id,
            "esewa_form": form,
            "checkout_url": None,
            "updated_at": datetime.now(UTC),
        }
    elif settings.payment_provider == "khalti":
        from app.services.payment_gateways import GatewayError, khalti_initiate

        base = return_url_base or settings.payment_return_url_base
        try:
            init = await khalti_initiate(
                amount_paisa=round(amount * 100),
                purchase_order_id=payment_id,
                purchase_order_name=f"EMI for loan {loan_id}",
                return_url=f"{base}/payments/return",
                website_url=settings.payment_website_url,
                customer=customer or {},
            )
        except GatewayError:
            await database[PAYMENTS_COLLECTION].update_one(
                {"_id": document["_id"]},
                {"$set": {"status": FAILED, "updated_at": datetime.now(UTC)}},
            )
            raise
        updates = {
            "provider": "khalti",
            "provider_ref": init["provider_ref"],
            "checkout_url": init["checkout_url"],
            "updated_at": datetime.now(UTC),
        }
    else:
        updates = {"checkout_url": f"/payments/{payment_id}/checkout"}

    await database[PAYMENTS_COLLECTION].update_one({"_id": document["_id"]}, {"$set": updates})
    document.update(updates)
    return document


def compute_prepayment_fee(amount: float) -> dict[str, float]:
    """Flat bank fee + percentage of the advance amount."""
    settings = get_settings()
    percent_fee = round(float(amount) * settings.prepayment_fee_percent / 100, 2)
    flat_fee = round(settings.prepayment_flat_fee, 2)
    total_fee = round(flat_fee + percent_fee, 2)
    return {
        "flat_fee": flat_fee,
        "percent_fee": percent_fee,
        "total_fee": total_fee,
        "total_charge": round(float(amount) + total_fee, 2),
    }


async def _build_gateway_updates(
    *,
    database: AsyncIOMotorDatabase,
    payment_id: str,
    amount: float,
    purchase_name: str,
    return_url_base: str | None,
    customer: dict[str, Any] | None,
) -> dict[str, Any]:
    settings = get_settings()
    base = return_url_base or settings.payment_return_url_base
    if settings.payment_provider == "esewa":
        from app.services.payment_gateways import esewa_build_form

        form = esewa_build_form(
            amount=amount,
            transaction_uuid=payment_id,
            success_url=f"{base}/payments/return",
            failure_url=f"{base}/payments/return?status=failed",
        )
        return {
            "provider": "esewa",
            "provider_ref": payment_id,
            "esewa_form": form,
            "checkout_url": None,
            "updated_at": datetime.now(UTC),
        }
    if settings.payment_provider == "khalti":
        from app.services.payment_gateways import khalti_initiate

        init = await khalti_initiate(
            amount_paisa=round(amount * 100),
            purchase_order_id=payment_id,
            purchase_order_name=purchase_name,
            return_url=f"{base}/payments/return",
            website_url=settings.payment_website_url,
            customer=customer or {},
        )
        return {
            "provider": "khalti",
            "provider_ref": init["provider_ref"],
            "checkout_url": init["checkout_url"],
            "updated_at": datetime.now(UTC),
        }
    return {"checkout_url": f"/payments/{payment_id}/checkout", "updated_at": datetime.now(UTC)}


async def initiate_prepayment(
    database: AsyncIOMotorDatabase,
    loan_id: str,
    applicant_id: str,
    principal_amount: float,
    *,
    return_url_base: str | None = None,
    customer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a PENDING advance-payment intent for a lump sum (1..outstanding).

    The customer is charged the principal amount plus a flat fee + percentage;
    on settlement only the principal reduces the outstanding balance.
    """
    if not ObjectId.is_valid(loan_id):
        raise LoanAccountNotFoundError
    loan = await database["loan_accounts"].find_one(
        {"_id": ObjectId(loan_id), "applicant_id": applicant_id}
    )
    if loan is None:
        raise LoanAccountNotFoundError
    if loan.get("status") != "active":
        raise LoanAccountStatusError

    outstanding = float(loan.get("outstanding_balance") or 0)
    principal = round(float(principal_amount), 2)
    if principal < 1 or principal > outstanding:
        raise PrepaymentAmountError

    fee = compute_prepayment_fee(principal)
    now = await simulated_now(database)
    document = {
        "loan_id": loan_id,
        "applicant_id": applicant_id,
        "amount": fee["total_charge"],
        "kind": PREPAYMENT_KIND,
        "prepay_principal": principal,
        "fee_flat": fee["flat_fee"],
        "fee_percent": fee["percent_fee"],
        "fee_total": fee["total_fee"],
        "status": PENDING,
        "provider": "mock_gateway",
        "provider_ref": uuid4().hex,
        "idempotency_key": uuid4().hex,
        "amount_paid": None,
        "settled_at": None,
        "checkout_url": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await database[PAYMENTS_COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    payment_id = str(document["_id"])

    updates = await _build_gateway_updates(
        database=database,
        payment_id=payment_id,
        amount=fee["total_charge"],
        purchase_name=f"Advance payment for loan {loan_id}",
        return_url_base=return_url_base,
        customer=customer,
    )
    await database[PAYMENTS_COLLECTION].update_one({"_id": document["_id"]}, {"$set": updates})
    document.update(updates)
    return document


async def _settle(database: AsyncIOMotorDatabase, payment: dict[str, Any]) -> dict[str, Any]:
    """Apply a successful payment to its loan (idempotent)."""
    if payment.get("status") == SUCCESS:
        return payment  # already settled

    try:
        if payment.get("kind") == PREPAYMENT_KIND:
            loan = await record_prepayment(
                database,
                str(payment["loan_id"]),
                str(payment["applicant_id"]),
                float(payment.get("prepay_principal") or 0),
            )
        else:
            loan = await record_payment(
                database, str(payment["loan_id"]), str(payment["applicant_id"])
            )
        amount_paid = loan.get("_last_payment", payment.get("amount"))
    except (LoanAccountNotFoundError, LoanAccountStatusError):
        # Loan gone or already closed — mark failed rather than raising.
        return await database[PAYMENTS_COLLECTION].find_one_and_update(
            {"_id": payment["_id"]},
            {"$set": {"status": FAILED, "updated_at": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    # Snapshot the loan after payment so the receipt is self-contained.
    return await database[PAYMENTS_COLLECTION].find_one_and_update(
        {"_id": payment["_id"]},
        {
            "$set": {
                "status": SUCCESS,
                "amount_paid": amount_paid,
                "outstanding_after": loan.get("outstanding_balance"),
                "installments_paid_after": loan.get("installments_paid"),
                "installments_total": loan.get("installments_total"),
                "next_due_date": loan.get("next_due_date"),
                "settled_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )


async def verify_payment(
    database: AsyncIOMotorDatabase,
    provider_ref: str,
    applicant_id: str,
) -> dict[str, Any]:
    """Confirm a real-rail payment via server-side lookup, then settle it.

    Called when the gateway redirects the customer back. We never trust the
    redirect params — the authoritative status comes from the gateway lookup.
    """
    payment = await database[PAYMENTS_COLLECTION].find_one(
        {"provider_ref": provider_ref, "applicant_id": applicant_id}
    )
    if payment is None:
        raise PaymentNotFoundError
    if payment.get("status") == SUCCESS:
        return payment  # idempotent

    # Confirm with the authoritative status API for whichever rail was used.
    if payment.get("provider") == "esewa":
        from app.services.payment_gateways import esewa_status_check

        result = await esewa_status_check(
            transaction_uuid=provider_ref,
            total_amount=float(payment.get("amount") or 0),
        )
    else:
        from app.services.payment_gateways import khalti_lookup

        result = await khalti_lookup(provider_ref)
    if result["status"] == SUCCESS:
        return await _settle(database, payment)

    new_status = FAILED if result["status"] == FAILED else PENDING
    return await database[PAYMENTS_COLLECTION].find_one_and_update(
        {"_id": payment["_id"]},
        {"$set": {"status": new_status, "updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )


async def get_payment_for_customer(
    database: AsyncIOMotorDatabase,
    payment_id: str,
    applicant_id: str,
) -> dict[str, Any] | None:
    """Fetch a payment only if it belongs to this customer (data isolation)."""
    if not ObjectId.is_valid(payment_id):
        return None
    return await database[PAYMENTS_COLLECTION].find_one(
        {"_id": ObjectId(payment_id), "applicant_id": applicant_id}
    )


async def process_webhook(
    database: AsyncIOMotorDatabase,
    provider_ref: str,
    result_status: str,
    signature: str,
) -> dict[str, Any]:
    """Verify the gateway signature and settle (or fail) the payment idempotently."""
    secret = get_settings().payment_webhook_secret
    if not verify_signature(webhook_payload(provider_ref, result_status), signature, secret):
        raise PaymentSignatureError

    payment = await database[PAYMENTS_COLLECTION].find_one({"provider_ref": provider_ref})
    if payment is None:
        raise PaymentNotFoundError

    if result_status == SUCCESS:
        return await _settle(database, payment)

    updated = await database[PAYMENTS_COLLECTION].find_one_and_update(
        {"_id": payment["_id"]},
        {"$set": {"status": FAILED, "updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )
    return updated


async def simulate_gateway_settlement(
    database: AsyncIOMotorDatabase,
    payment_id: str,
    applicant_id: str,
) -> dict[str, Any]:
    """Dev/demo helper: emulate the gateway confirming a payment via the webhook.

    Signs the payload with the server secret and runs the same webhook path, so
    the settlement is identical to a real gateway callback.
    """
    if not ObjectId.is_valid(payment_id):
        raise PaymentNotFoundError
    payment = await database[PAYMENTS_COLLECTION].find_one(
        {"_id": ObjectId(payment_id), "applicant_id": applicant_id}
    )
    if payment is None:
        raise PaymentNotFoundError

    provider_ref = str(payment["provider_ref"])
    signature = sign_webhook(provider_ref, SUCCESS)
    return await process_webhook(database, provider_ref, SUCCESS, signature)
