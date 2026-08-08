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
from app.services.email_service import send_email
from app.services.loan_account_service import (
    LoanAccountNotFoundError,
    LoanAccountStatusError,
    record_payment,
    record_prepayment,
)
from app.services.notification_service import create_notification

PAYMENTS_COLLECTION = "payments"

PENDING = "pending"
SUCCESS = "success"
FAILED = "failed"
# Customer scanned the QR and marked it paid; awaiting officer confirmation.
AWAITING_CONFIRMATION = "awaiting_confirmation"
# Officer looked at the receipt and rejected it (wrong account / amount / no match).
REJECTED = "rejected"

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
    method: str | None = None,
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
    # The customer may pick a method per payment; default to the configured rail.
    provider = (method or settings.payment_provider or "mock").lower()
    now = await simulated_now(database)
    # The EMI is payable at any time on an active loan (the earlier 7-day window
    # restriction was removed so a customer is never blocked from paying). Any
    # accrued late fee is charged on top of the EMI.
    emi_amount = float(loan.get("monthly_emi") or 0)
    penalty_amount = round(float(loan.get("penalty_due") or 0), 2)
    amount = round(emi_amount + penalty_amount, 2)
    document = {
        "loan_id": loan_id,
        "applicant_id": applicant_id,
        "amount": amount,
        "emi_amount": emi_amount,
        "penalty_amount": penalty_amount,
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

    if provider == "qr":
        # Scan-a-personal-QR flow: show the merchant's eSewa QR on our checkout
        # page; the customer pays there and an officer confirms receipt.
        updates = {
            "provider": "esewa_qr",
            "checkout_url": f"/payments/{payment_id}/checkout",
            "merchant_name": settings.merchant_qr_name,
            "merchant_phone": settings.merchant_qr_phone,
            "qr_url": settings.merchant_qr_url,
            "updated_at": datetime.now(UTC),
        }
    elif provider == "esewa":
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
    elif provider == "khalti":
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
        updates = {
            "provider": "mock_gateway",
            "checkout_url": f"/payments/{payment_id}/checkout",
        }

    await database[PAYMENTS_COLLECTION].update_one({"_id": document["_id"]}, {"$set": updates})
    document.update(updates)

    # Demo mode: the mock rail settles the payment immediately (no external
    # gateway), so the customer goes straight to a paid receipt and the receipt
    # email is sent — reliable for a localhost demo/defense.
    if provider == "mock":
        return await _settle(database, document)
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
    method: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    provider = (method or settings.payment_provider or "mock").lower()
    base = return_url_base or settings.payment_return_url_base
    if provider == "qr":
        return {
            "provider": "esewa_qr",
            "checkout_url": f"/payments/{payment_id}/checkout",
            "merchant_name": settings.merchant_qr_name,
            "merchant_phone": settings.merchant_qr_phone,
            "qr_url": settings.merchant_qr_url,
            "updated_at": datetime.now(UTC),
        }
    if provider == "esewa":
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
    if provider == "khalti":
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
    method: str | None = None,
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
        method=method,
    )
    await database[PAYMENTS_COLLECTION].update_one({"_id": document["_id"]}, {"$set": updates})
    document.update(updates)

    # Demo mode: settle the advance payment immediately (see initiate_payment).
    provider = (method or get_settings().payment_provider or "mock").lower()
    if provider == "mock":
        return await _settle(database, document)
    return document


async def _settle(
    database: AsyncIOMotorDatabase,
    payment: dict[str, Any],
    *,
    verified_amount: float | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a successful payment to its loan (idempotent).

    ``verified_amount`` is the officer-reviewed deposit amount (from the bank
    receipt). It only affects EMI payments — a deposit short of the monthly EMI
    is applied as a partial payment (see ``record_payment``). Gateway-confirmed
    payments (webhook/eSewa/Khalti) never pass this — the rail already collected
    the exact amount, so the full EMI is credited as before.
    """
    if payment.get("status") == SUCCESS:
        return payment  # already settled

    is_partial = False
    shortfall = 0.0
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
                database,
                str(payment["loan_id"]),
                str(payment["applicant_id"]),
                verified_amount=verified_amount,
            )
            is_partial = bool(loan.get("_is_partial"))
            shortfall = float(loan.get("_shortfall") or 0)
        amount_paid = loan.get("_last_payment", payment.get("amount"))
    except (LoanAccountNotFoundError, LoanAccountStatusError):
        # Loan gone or already closed — mark failed rather than raising.
        return await database[PAYMENTS_COLLECTION].find_one_and_update(
            {"_id": payment["_id"]},
            {"$set": {"status": FAILED, "updated_at": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    # Snapshot the loan after payment so the receipt is self-contained.
    fields: dict[str, Any] = {
        "status": SUCCESS,
        "amount_paid": amount_paid,
        "outstanding_after": loan.get("outstanding_balance"),
        "installments_paid_after": loan.get("installments_paid"),
        "installments_total": loan.get("installments_total"),
        "next_due_date": loan.get("next_due_date"),
        "is_partial": is_partial,
        "shortfall": shortfall,
        "settled_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    if extra_fields:
        fields.update(extra_fields)

    settled = await database[PAYMENTS_COLLECTION].find_one_and_update(
        {"_id": payment["_id"]},
        {"$set": fields},
        return_document=ReturnDocument.AFTER,
    )
    # A settled EMI payment that included a late fee clears the loan's accrued
    # penalty (the fee was charged on top of the EMI).
    if (
        payment.get("kind") != PREPAYMENT_KIND
        and float(payment.get("penalty_amount") or 0) > 0
    ):
        await database["loan_accounts"].update_one(
            {"_id": ObjectId(str(payment["loan_id"]))}
            if ObjectId.is_valid(str(payment.get("loan_id")))
            else {"_id": payment.get("loan_id")},
            {"$set": {"penalty_due": 0.0}},
        )

    # Email the customer a payment receipt. This runs exactly once per payment,
    # because _settle short-circuits when the payment is already SUCCESS.
    if settled is not None:
        await _send_payment_receipt_email(database, settled)
        # In-app notifications (payment received + loan closed) and, if the loan
        # is now fully repaid, a closure email. Best-effort — never blocks a
        # settled payment.
        await _notify_after_settlement(database, settled, loan)
    return settled


async def _notify_after_settlement(
    database: AsyncIOMotorDatabase,
    payment: dict[str, Any],
    loan: dict[str, Any],
) -> None:
    """Post-settlement in-app notifications (and loan-closed email)."""
    applicant_id = str(payment.get("applicant_id") or "")
    if not applicant_id:
        return

    is_prepayment = payment.get("kind") == PREPAYMENT_KIND
    amount = payment.get("amount_paid")
    amount_text = f"NPR {amount}" if amount is not None else f"NPR {payment.get('amount')}"
    kind_text = "advance payment" if is_prepayment else "EMI payment"
    balance = payment.get("outstanding_after")
    message = f"Your {kind_text} of {amount_text} was received."
    if balance is not None:
        message += f" Remaining balance: NPR {balance}."

    try:
        await create_notification(
            database=database,
            user_id=applicant_id,
            title="Payment received",
            message=message,
        )
    except Exception:  # noqa: BLE001 - notifications are best-effort
        pass

    # Loan fully repaid -> closure notification + email.
    if str(loan.get("status")) == "completed":
        try:
            await create_notification(
                database=database,
                user_id=applicant_id,
                title="Loan fully repaid",
                message="Congratulations! Your loan is now fully repaid and has been closed.",
            )
        except Exception:  # noqa: BLE001
            pass
        await _send_loan_closed_email(database, payment)


async def _send_loan_closed_email(
    database: AsyncIOMotorDatabase, payment: dict[str, Any]
) -> None:
    """Email the customer that their loan is fully repaid and closed (best-effort)."""
    applicant_id = str(payment.get("applicant_id") or "")
    user = None
    if ObjectId.is_valid(applicant_id):
        user = await database["users"].find_one({"_id": ObjectId(applicant_id)})
    email = (user or {}).get("email")
    if not email:
        return

    body = "\n".join(
        [
            "Dear customer,",
            "",
            "Congratulations! Your loan has been fully repaid and is now closed.",
            f"Final transaction reference: {payment.get('provider_ref')}",
            "",
            "Thank you for banking with Sajilo Loan.",
            "",
            "— Sajilo Loan",
        ]
    )
    try:
        await send_email(
            database=database,
            to_email=str(email),
            subject="Sajilo Loan — your loan is fully repaid",
            body=body,
        )
    except Exception:  # noqa: BLE001 - closure email is best-effort
        pass


async def _send_payment_receipt_email(
    database: AsyncIOMotorDatabase, payment: dict[str, Any]
) -> None:
    """Send a payment-confirmation email to the paying customer (best-effort)."""
    applicant_id = str(payment.get("applicant_id") or "")
    user = None
    if ObjectId.is_valid(applicant_id):
        user = await database["users"].find_one({"_id": ObjectId(applicant_id)})
    email = (user or {}).get("email")
    if not email:
        return

    is_prepayment = payment.get("kind") == PREPAYMENT_KIND
    amount = payment.get("amount_paid")
    amount_text = f"NPR {amount}" if amount is not None else f"NPR {payment.get('amount')}"
    kind_text = "advance (lump-sum) payment" if is_prepayment else "EMI payment"

    lines = [
        f"Dear customer,\n",
        f"We have received your {kind_text} of {amount_text}. Thank you.\n",
        f"Transaction reference: {payment.get('provider_ref')}",
        f"Method: {str(payment.get('provider') or 'n/a').replace('_', ' ')}",
    ]
    if payment.get("outstanding_after") is not None:
        lines.append(f"Remaining balance: NPR {payment.get('outstanding_after')}")
    if payment.get("installments_paid_after") is not None and payment.get("installments_total") is not None:
        lines.append(
            f"Installments paid: {payment.get('installments_paid_after')}/{payment.get('installments_total')}"
        )
    if payment.get("next_due_date") is not None:
        lines.append(f"Next EMI due: {str(payment.get('next_due_date'))[:10]}")
    if payment.get("is_partial"):
        lines.append(
            f"\nNote: this was a partial payment. NPR {payment.get('shortfall')} is still due to "
            "complete this installment; the due date has not moved."
        )
    lines.append("\n— Sajilo Loan")

    try:
        await send_email(
            database=database,
            to_email=str(email),
            subject=f"Sajilo Loan — payment received ({amount_text})",
            body="\n".join(lines),
        )
    except Exception:  # noqa: BLE001 - receipts are best-effort, never block settlement
        pass


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


async def list_payments_for_applicant(
    database: AsyncIOMotorDatabase,
    applicant_id: str,
) -> list[dict[str, Any]]:
    """Every payment (statement history) for one customer, newest first."""
    cursor = database[PAYMENTS_COLLECTION].find(
        {"applicant_id": applicant_id}
    ).sort("created_at", -1)
    return [document async for document in cursor]


async def mark_payment_submitted(
    database: AsyncIOMotorDatabase,
    payment_id: str,
    applicant_id: str,
    *,
    depositor_account_number: str,
    amount_deposited: float,
    remarks: str | None = None,
) -> dict[str, Any]:
    """Customer scanned the QR and paid — attach their deposit receipt details and
    mark the payment awaiting officer confirmation.

    ``depositor_account_number`` and ``amount_deposited`` are what the customer
    read off their own bank/eSewa receipt after paying the merchant QR. An
    officer later cross-checks these against the bank statement before the EMI
    is cut (see ``confirm_payment``).
    """
    if not ObjectId.is_valid(payment_id):
        raise PaymentNotFoundError
    payment = await database[PAYMENTS_COLLECTION].find_one(
        {"_id": ObjectId(payment_id), "applicant_id": applicant_id}
    )
    if payment is None:
        raise PaymentNotFoundError
    if payment.get("status") == SUCCESS:
        return payment  # already settled
    return await database[PAYMENTS_COLLECTION].find_one_and_update(
        {"_id": payment["_id"]},
        {
            "$set": {
                "status": AWAITING_CONFIRMATION,
                "depositor_account_number": depositor_account_number.strip(),
                "amount_deposited": round(float(amount_deposited), 2),
                "customer_remarks": (remarks or "").strip() or None,
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )


async def confirm_payment(
    database: AsyncIOMotorDatabase,
    payment_id: str,
    *,
    officer_id: str | None = None,
    verified_amount: float | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Officer confirms a receipt after reviewing the account number and amount
    deposited — settle it, cutting the EMI by what was actually verified.

    ``verified_amount`` is what the officer read off the bank statement. If
    omitted, the amount the customer declared on their receipt is used; if that
    is also missing (legacy/simulated payments), the full EMI is assumed.
    """
    if not ObjectId.is_valid(payment_id):
        raise PaymentNotFoundError
    payment = await database[PAYMENTS_COLLECTION].find_one({"_id": ObjectId(payment_id)})
    if payment is None:
        raise PaymentNotFoundError

    amount = verified_amount
    if amount is None:
        amount = payment.get("amount_deposited")

    extra_fields: dict[str, Any] = {
        "verified_amount": round(float(amount), 2) if amount is not None else None,
        "officer_notes": (notes or "").strip() or None,
        "confirmed_by": officer_id,
    }
    return await _settle(
        database,
        payment,
        verified_amount=float(amount) if amount is not None else None,
        extra_fields=extra_fields,
    )


async def reject_payment(
    database: AsyncIOMotorDatabase,
    payment_id: str,
    *,
    officer_id: str | None = None,
    reason: str,
) -> dict[str, Any]:
    """Officer reviewed the receipt and could not match it — reject it.

    The customer sees the reason and can resubmit (e.g. wrong account number,
    amount doesn't match any deposit on the statement).
    """
    if not ObjectId.is_valid(payment_id):
        raise PaymentNotFoundError
    payment = await database[PAYMENTS_COLLECTION].find_one({"_id": ObjectId(payment_id)})
    if payment is None:
        raise PaymentNotFoundError
    if payment.get("status") == SUCCESS:
        return payment  # already settled, nothing to reject

    return await database[PAYMENTS_COLLECTION].find_one_and_update(
        {"_id": payment["_id"]},
        {
            "$set": {
                "status": REJECTED,
                "officer_notes": reason.strip(),
                "confirmed_by": officer_id,
                "updated_at": datetime.now(UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )


async def list_pending_confirmations(
    database: AsyncIOMotorDatabase,
) -> list[dict[str, Any]]:
    """QR payments the customer marked paid, awaiting officer confirmation."""
    cursor = database[PAYMENTS_COLLECTION].find(
        {"status": AWAITING_CONFIRMATION}
    ).sort("updated_at", -1)
    return [document async for document in cursor]


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
