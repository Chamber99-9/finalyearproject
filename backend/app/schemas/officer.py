from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.application import ApplicationStatus
from app.models.document import DocumentType
from app.models.document_request import DocumentRequestStatus
from app.schemas.application import ApplicationResponse
from app.schemas.document import DocumentResponse
from app.schemas.flags import ApplicationFlagsResponse
from app.schemas.ocr import OCRResultResponse
from app.schemas.risk import CreditRiskResponse


class ApplicationStatusUpdateRequest(BaseModel):
    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AdditionalDocumentRequestCreate(BaseModel):
    document_types: list[DocumentType] = Field(..., min_length=1)
    message: str | None = Field(default=None, max_length=500)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class InterestRateUpdateRequest(BaseModel):
    """Override the interest rate applied to a single application (admin only).

    Recalculates EMI, total interest and total repayment when saved.
    """

    interest_rate: float = Field(..., gt=0)


class OfficerVerificationUpdate(BaseModel):
    """Officer sign-off on document/identity checks for an application."""

    pan_verified: bool | None = None
    income_verified: bool | None = None
    salary_statement_verified: bool | None = None
    stamp_verified: bool | None = None
    signature_verified: bool | None = None
    collateral_verified: bool | None = None
    valuation_report_verified: bool | None = None
    recommendation_letter_verified: bool | None = None


class CounterOfferCreate(BaseModel):
    offered_loan_amount: float = Field(..., gt=0)
    message: str = Field(..., min_length=3, max_length=500)

    @field_validator("message")
    @classmethod
    def strip_counter_offer_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty")
        return value


class AdditionalDocumentRequestResponse(BaseModel):
    id: str
    application_id: str
    requested_by: str
    document_types: list[DocumentType]
    message: str | None
    status: DocumentRequestStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OfficerApplicationDetailResponse(BaseModel):
    application: ApplicationResponse
    documents: list[DocumentResponse]
    ocr_results: list[OCRResultResponse]
    name_match: dict[str, Any] | None = None
    credit_risk_score: CreditRiskResponse | None
    suspicious_flags: ApplicationFlagsResponse | None

    model_config = ConfigDict(from_attributes=True)
