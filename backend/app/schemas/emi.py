"""Request/response schemas for the EMI calculator module."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import LoanType
from app.services.emi_service import TenureUnit


class EMICalculateRequest(BaseModel):
    """Input for the standalone POST /emi/calculate endpoint.

    Validation (requirement #14):
        loan_amount > 0, annual_interest_rate >= 0, tenure > 0.
    """

    loan_amount: float = Field(..., gt=0)
    annual_interest_rate: float = Field(..., ge=0)
    tenure: int = Field(..., gt=0)
    tenure_unit: TenureUnit = TenureUnit.YEARS

    model_config = ConfigDict(use_enum_values=True)


class EMIResponse(BaseModel):
    """Result returned by calculate_emi()."""

    monthly_emi: float
    total_interest: float
    total_payment: float

    model_config = ConfigDict(from_attributes=True)


class EMIPreviewRequest(BaseModel):
    """Customer-facing preview: amount + tenure + loan type. The rate is derived
    from the bank engine (base + type spread + tenure adjustment).

    Validation: loan_amount > 0, tenure > 0.
    """

    loan_amount: float = Field(..., gt=0)
    tenure: int = Field(..., gt=0)
    tenure_unit: TenureUnit = TenureUnit.YEARS
    loan_type: LoanType = LoanType.PERSONAL

    model_config = ConfigDict(use_enum_values=True)


class EMIPreviewResponse(BaseModel):
    """EMI preview including the bank rate that was applied."""

    interest_rate_used: float
    monthly_emi: float
    total_interest: float
    total_payment: float

    model_config = ConfigDict(from_attributes=True)


class AmortizationEntry(BaseModel):
    """A single installment row in the amortization schedule."""

    month: int
    emi: float
    principal_paid: float
    interest_paid: float
    remaining_balance: float


class AmortizationScheduleResponse(BaseModel):
    """Full amortization schedule for a stored application."""

    application_id: str
    loan_amount: float
    annual_interest_rate: float
    tenure_months: int
    monthly_emi: float
    total_interest: float
    total_payment: float
    schedule: list[AmortizationEntry]
