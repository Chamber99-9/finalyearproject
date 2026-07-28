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
)
from app.services.loan_account_service import LoanAccountNotFoundError, LoanAccountStatusError
from app.services.payment_gateways import GatewayError
from app.services.payment_service import (
    PaymentNotFoundError,
    PaymentSignatureError,
    get_payment_for_customer,
    initiate_payment,
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


@payments_router.post("/{payment_id}/simulate", response_model=PaymentResponse)
async def simulate_payment(
    payment_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Emulate the gateway confirming the payment (runs the real webhook path)."""
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
