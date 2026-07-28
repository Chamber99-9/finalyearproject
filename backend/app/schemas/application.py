from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.application import (
    ApplicationStatus,
    EmploymentType,
    LoanType,
    RepaymentHistory,
    SavingsBuffer,
)
from app.services.emi_service import TenureUnit


class ApplicationCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    citizenship_number: str = Field(..., min_length=3, max_length=40)
    phone: str = Field(..., min_length=7, max_length=20)
    address: str = Field(..., min_length=3, max_length=200)
    loan_type: LoanType = LoanType.PERSONAL
    monthly_income: float = Field(..., gt=0)
    employment_type: EmploymentType
    existing_monthly_debt: float = Field(..., ge=0)
    requested_loan_amount: float = Field(..., gt=0)
    loan_duration_months: int = Field(..., ge=1, le=360)
    # Customer enters only the tenure (amount + tenure > 0). The interest rate is
    # bank-defined and applied by the system — never entered by the customer.
    loan_tenure: int = Field(..., ge=1)
    tenure_unit: TenureUnit = TenureUnit.YEARS
    loan_purpose: str = Field(..., min_length=3, max_length=300)
    dependents: int = Field(..., ge=0)
    savings_buffer: SavingsBuffer
    repayment_history: RepaymentHistory
    # PAN + collateral (collateral is required for non-instant loans above the
    # threshold — enforced on submit).
    pan_number: str | None = Field(None, min_length=9, max_length=9)
    collateral_type: str | None = Field(None, max_length=100)
    collateral_value: float | None = Field(None, ge=0)
    collateral_description: str | None = Field(None, max_length=300)

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value.isdigit() or len(value) != 9:
            raise ValueError("PAN number must be exactly 9 digits.")
        return value

    @field_validator(
        "full_name",
        "citizenship_number",
        "phone",
        "address",
        "loan_purpose",
    )
    @classmethod
    def strip_and_require_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        allowed = set("0123456789+-() ")
        if any(character not in allowed for character in value):
            raise ValueError("Phone can contain only digits, spaces, +, -, (, and )")
        return value


class ApplicationDraftCreateRequest(BaseModel):
    loan_type: LoanType = LoanType.PERSONAL


class CounterOfferResponseRequest(BaseModel):
    accepted: bool


class ApplicationUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=100)
    citizenship_number: str | None = Field(None, min_length=3, max_length=40)
    phone: str | None = Field(None, min_length=7, max_length=20)
    address: str | None = Field(None, min_length=3, max_length=200)
    loan_type: LoanType | None = None
    monthly_income: float | None = Field(None, gt=0)
    employment_type: EmploymentType | None = None
    existing_monthly_debt: float | None = Field(None, ge=0)
    requested_loan_amount: float | None = Field(None, gt=0)
    loan_duration_months: int | None = Field(None, ge=1, le=360)
    loan_tenure: int | None = Field(None, ge=1)
    tenure_unit: TenureUnit | None = None
    loan_purpose: str | None = Field(None, min_length=3, max_length=300)
    dependents: int | None = Field(None, ge=0)
    savings_buffer: SavingsBuffer | None = None
    repayment_history: RepaymentHistory | None = None
    pan_number: str | None = Field(None, min_length=9, max_length=9)
    collateral_type: str | None = Field(None, max_length=100)
    collateral_value: float | None = Field(None, ge=0)
    collateral_description: str | None = Field(None, max_length=300)

    @field_validator("pan_number")
    @classmethod
    def validate_optional_pan(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value.isdigit() or len(value) != 9:
            raise ValueError("PAN number must be exactly 9 digits.")
        return value

    @field_validator(
        "full_name",
        "citizenship_number",
        "phone",
        "address",
        "loan_purpose",
    )
    @classmethod
    def strip_optional_value(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty")
        return value

    @field_validator("phone")
    @classmethod
    def validate_optional_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = set("0123456789+-() ")
        if any(character not in allowed for character in value):
            raise ValueError("Phone can contain only digits, spaces, +, -, (, and )")
        return value


class ApplicationResponse(BaseModel):
    id: str
    applicant_id: str
    full_name: str | None = None
    citizenship_number: str | None = None
    phone: str | None = None
    address: str | None = None
    loan_type: LoanType
    monthly_income: float | None = None
    employment_type: EmploymentType | None = None
    existing_monthly_debt: float | None = None
    requested_loan_amount: float | None = None
    loan_duration_months: int | None = None
    # Bank-defined rate applied to this application + auto-calculated EMI outputs.
    interest_rate_used: float | None = None
    loan_tenure: int | None = None
    tenure_unit: TenureUnit | None = None
    monthly_emi: float | None = None
    total_interest: float | None = None
    total_payment: float | None = None
    emi_dti_ratio: float | None = None
    affordability: str | None = None
    pan_number: str | None = None
    collateral_type: str | None = None
    collateral_value: float | None = None
    collateral_description: str | None = None
    verification: dict | None = None
    loan_purpose: str | None = None
    dependents: int | None = None
    savings_buffer: SavingsBuffer | None = None
    repayment_history: RepaymentHistory | None = None
    offered_loan_amount: float | None = None
    offer_message: str | None = None
    offer_status: str | None = None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
