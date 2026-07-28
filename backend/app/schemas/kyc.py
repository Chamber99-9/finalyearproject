"""KYC (Know Your Customer) schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KycSubmitRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    pan_number: str = Field(..., min_length=9, max_length=9)
    citizenship_number: str = Field(..., min_length=3, max_length=40)
    date_of_birth: str = Field(..., min_length=4, max_length=20)

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) != 9:
            raise ValueError("PAN number must be exactly 9 digits.")
        return value


class KycResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    pan_number: str
    citizenship_number: str
    date_of_birth: str
    status: str
    checks: dict
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KycReviewRequest(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=300)
