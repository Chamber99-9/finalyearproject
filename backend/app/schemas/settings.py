"""Schemas for reading and updating bank-defined loan settings."""

from pydantic import BaseModel, ConfigDict, Field


class LoanInterestRateResponse(BaseModel):
    """Current bank interest rate for a loan type."""

    loan_type: str
    interest_rate: float

    model_config = ConfigDict(from_attributes=True)


class LoanInterestRateUpdateRequest(BaseModel):
    """Admin request to change the bank default interest rate (percent, > 0)."""

    interest_rate: float = Field(..., gt=0)
