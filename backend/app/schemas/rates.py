"""Schemas for the loan-type rate menu and rate quotes."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import LoanType
from app.services.emi_service import TenureUnit


class LoanTypeInfoResponse(BaseModel):
    """A loan product shown in the selection menu with its current rate spread."""

    loan_type: str
    label: str
    base_rate: float
    type_spread: float
    indicative_rate: float
    requires_collateral_above: float | None = None
    max_tenure_years: int

    model_config = ConfigDict(from_attributes=True)


class LoanRateQuoteRequest(BaseModel):
    """Ask for the effective rate for a loan type + tenure."""

    loan_type: LoanType = LoanType.PERSONAL
    tenure: int = Field(..., gt=0)
    tenure_unit: TenureUnit = TenureUnit.YEARS

    model_config = ConfigDict(use_enum_values=True)


class LoanRateQuoteResponse(BaseModel):
    """Effective rate breakdown for a specific selection."""

    loan_type: str
    base_rate: float
    type_spread: float
    tenure_adjustment: float
    effective_rate: float

    model_config = ConfigDict(from_attributes=True)
