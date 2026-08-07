"""Schemas for loan eligibility checks and mock verification."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import LoanType


class EligibilityCheckRequest(BaseModel):
    loan_type: LoanType = LoanType.PERSONAL
    loan_amount: float = Field(0, ge=0)
    monthly_income: float = Field(0, ge=0)

    model_config = ConfigDict(use_enum_values=True)


class EligibilityResponse(BaseModel):
    loan_type: str
    monthly_income: float
    requested_amount: float
    max_amount: float
    within_cap: bool
    min_amount: float = 0
    meets_minimum: bool = True
    requires_collateral: bool
    collateral_threshold: float
    instant_cap: float | None = None

    model_config = ConfigDict(from_attributes=True)


class PanCheckRequest(BaseModel):
    pan_number: str = Field(..., min_length=1, max_length=20)


class PanCheckResponse(BaseModel):
    pan_number: str
    valid_format: bool
    tax_registered: bool
    reason: str

    model_config = ConfigDict(from_attributes=True)


class SalaryCheckRequest(BaseModel):
    stated_monthly_income: float = Field(..., ge=0)
    declared_monthly_income: float = Field(..., ge=0)
    employer_name: str | None = None


class SalaryCheckResponse(BaseModel):
    valid: bool
    reason: str

    model_config = ConfigDict(from_attributes=True)
