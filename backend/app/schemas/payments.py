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
    # Personal-QR destination shown at checkout when provider=qr.
    merchant_name: str | None = None
    merchant_phone: str | None = None
    qr_url: str | None = None
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
    # Deposit receipt the customer submits after paying the QR (self-reported).
    depositor_account_number: str | None = None
    amount_deposited: float | None = None
    customer_remarks: str | None = None
    # Officer's review of the receipt above.
    verified_amount: float | None = None
    officer_notes: str | None = None
    confirmed_by: str | None = None
    # True when the verified deposit fell short of the EMI (partial payment).
    is_partial: bool | None = None
    shortfall: float | None = None
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


class PaymentReceiptSubmit(BaseModel):
    """Customer's self-reported deposit receipt, submitted after paying the QR."""

    depositor_account_number: str = Field(..., min_length=4, max_length=34)
    amount_deposited: float = Field(..., gt=0)
    remarks: str | None = Field(default=None, max_length=280)


class PaymentConfirmRequest(BaseModel):
    """Officer's review outcome after checking the account number and amount
    deposited against the bank statement."""

    verified_amount: float | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=280)


class PaymentRejectRequest(BaseModel):
    """Officer rejects a receipt that doesn't match the bank statement."""

    reason: str = Field(..., min_length=3, max_length=280)
