"""Payment routes: intent, gateway webhook, and a dev settlement simulator.

    POST /loans/{loan_id}/payments/initiate  -> create a pending payment intent
    POST /payments/webhook                    -> gateway callback (HMAC-signed)
    POST /payments/{payment_id}/simulate      -> dev: emulate gateway success
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_customer
from app.config import get_settings
from app.database import get_database
from app.schemas.payments import (
    PaymentResponse,
    PaymentVerifyRequest,
    PaymentWebhookRequest,
    PrepaymentRequest,
)
from app.services.loan_account_service import LoanAccountNotFoundError, LoanAccountStatusError
from app.services.payment_gateways import GatewayError
from app.services.payment_service import (
    PaymentNotFoundError,
    PaymentSignatureError,
    PaymentWindowError,
    PrepaymentAmountError,
    get_payment_for_customer,
    initiate_payment,
    initiate_prepayment,
    mark_payment_submitted,
    process_webhook,
    serialize_payment,
    simulate_gateway_settlement,
    verify_payment,
)

loans_payment_router = APIRouter(prefix="/loans", tags=["payments"])
payments_router = APIRouter(prefix="/payments", tags=["payments"])


@loans_payment_router.post("/{loan_id}/payments/initiate", response_model=PaymentResponse)
async def initiate_loan_payment(
    loan_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    try:
        payment = await initiate_payment(
            database,
            loan_id,
            applicant_id,
            return_url_base=get_settings().payment_return_url_base,
            customer={
                "name": current_user.get("full_name"),
                "email": current_user.get("email"),
                "phone": current_user.get("phone"),
            },
        )
    except GatewayError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment gateway could not start the payment.",
        ) from error
    except LoanAccountNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan account not found.",
        ) from error
    except LoanAccountStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This loan is not active; no payment is due.",
        ) from error
    except PaymentWindowError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This EMI is not payable yet. You can pay from "
                f"{error.payable_from.date()} (within the days before the due date)."
            ),
        ) from error
    return serialize_payment(payment)


@loans_payment_router.post("/{loan_id}/payments/prepay-initiate", response_model=PaymentResponse)
async def initiate_loan_prepayment(
    loan_id: str,
    payload: PrepaymentRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Start an advance (lump-sum) payment of 1..outstanding, with fees."""
    applicant_id = get_authenticated_user_id(current_user)
    try:
        payment = await initiate_prepayment(
            database,
            loan_id,
            applicant_id,
            payload.amount,
            return_url_base=get_settings().payment_return_url_base,
            customer={
                "name": current_user.get("full_name"),
                "email": current_user.get("email"),
                "phone": current_user.get("phone"),
            },
        )
    except GatewayError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment gateway could not start the payment.",
        ) from error
    except LoanAccountNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan account not found.",
        ) from error
    except LoanAccountStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This loan is not active.",
        ) from error
    except PrepaymentAmountError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Advance amount must be between 1 and your outstanding balance.",
        ) from error
    return serialize_payment(payment)


@payments_router.get("/{payment_id}", response_model=PaymentResponse)
async def read_payment(
    payment_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Fetch one of the customer's own payments (checkout + receipt)."""
    applicant_id = get_authenticated_user_id(current_user)
    payment = await get_payment_for_customer(database, payment_id, applicant_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    return serialize_payment(payment)


@payments_router.post("/{payment_id}/submitted", response_model=PaymentResponse)
async def mark_payment_submitted_route(
    payment_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Customer confirms they scanned the QR and paid; awaits officer confirmation."""
    applicant_id = get_authenticated_user_id(current_user)
    try:
        payment = await mark_payment_submitted(database, payment_id, applicant_id)
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        ) from error
    return serialize_payment(payment)


@payments_router.post("/{payment_id}/simulate", response_model=PaymentResponse)
async def simulate_payment(
    payment_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Emulate the gateway confirming the payment (runs the real webhook path).

    Dev/demo only: this settles a payment without real money, so it is disabled
    outside development where a real rail (eSewa) must confirm the payment.
    """
    if get_settings().app_env.lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payment simulation is disabled outside development.",
        )
    applicant_id = get_authenticated_user_id(current_user)
    try:
        payment = await simulate_gateway_settlement(database, payment_id, applicant_id)
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        ) from error
    return serialize_payment(payment)


@payments_router.post("/verify", response_model=PaymentResponse)
async def verify_payment_route(
    payload: PaymentVerifyRequest,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Confirm a real-rail payment after the gateway redirects back."""
    applicant_id = get_authenticated_user_id(current_user)
    try:
        payment = await verify_payment(database, payload.provider_ref, applicant_id)
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        ) from error
    except GatewayError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not verify the payment with the gateway.",
        ) from error
    return serialize_payment(payment)


@payments_router.post("/webhook", response_model=PaymentResponse)
async def payment_webhook(
    payload: PaymentWebhookRequest,
    x_signature: Annotated[str | None, Header()] = None,
    database: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Gateway callback. The signature is HMAC-SHA256 over the payload body."""
    try:
        payment = await process_webhook(
            database,
            provider_ref=payload.provider_ref,
            result_status=payload.status,
            signature=x_signature or "",
        )
    except PaymentSignatureError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        ) from error
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        ) from error
    return serialize_payment(payment)
