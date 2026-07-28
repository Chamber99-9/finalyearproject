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


class BaseLendingRateResponse(BaseModel):
    """Current bank base lending rate (percent)."""

    base_rate: float

    model_config = ConfigDict(from_attributes=True)


class BaseLendingRateUpdateRequest(BaseModel):
    """Admin request to change the bank base lending rate (percent, > 0)."""

    base_rate: float = Field(..., gt=0)
