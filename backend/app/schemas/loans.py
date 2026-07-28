"""Schemas for disbursed loan accounts and payments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoanAccountResponse(BaseModel):
    id: str
    application_id: str
    applicant_id: str
    principal: float
    interest_rate: float
    tenure_months: int
    monthly_emi: float
    total_payment: float
    total_interest: float
    outstanding_balance: float
    installments_paid: int
    installments_total: int
    missed_installments: int
    next_due_date: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    amount_paid: float
    loan: LoanAccountResponse


class RemindersResponse(BaseModel):
    reminded: int


class OverdueResponse(BaseModel):
    overdue: int
    blacklisted: int
