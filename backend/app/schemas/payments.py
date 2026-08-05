"""Payment intent + webhook schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentResponse(BaseModel):
    id: str
    loan_id: str
    applicant_id: str
    amount: float
    status: str
    provider: str
    provider_ref: str
    checkout_url: str | None = None
    # eSewa auto-submit form (action URL + signed fields) when provider=esewa.
    esewa_form: dict | None = None
    # Advance-payment fields (present when kind=prepayment).
    kind: str | None = None
    prepay_principal: float | None = None
    fee_flat: float | None = None
    fee_percent: float | None = None
    fee_total: float | None = None
    amount_paid: float | None = None
    outstanding_after: float | None = None
    installments_paid_after: int | None = None
    installments_total: int | None = None
    next_due_date: datetime | None = None
    settled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentWebhookRequest(BaseModel):
    provider_ref: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class PaymentVerifyRequest(BaseModel):
    """Real-rail return: the gateway reference (Khalti pidx) to confirm."""

    provider_ref: str = Field(..., min_length=1)


class PrepaymentRequest(BaseModel):
    """Advance lump-sum payment amount (1 .. outstanding balance)."""

    amount: float = Field(..., gt=0)
