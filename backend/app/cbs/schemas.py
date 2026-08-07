"""CBS request/response contracts (Customer Account + Loan Account modules)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.cbs.models import AccountType, DepositAccountStatus


# --- CIF --------------------------------------------------------------------

class CifCreateRequest(BaseModel):
    los_user_id: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=2, max_length=100)
    citizenship_no: str | None = None
    pan: str | None = None
    phone: str | None = None
    kyc_status: str = "not_started"


class CifResponse(BaseModel):
    cif_no: str
    los_user_id: str
    full_name: str
    citizenship_no: str | None = None
    pan: str | None = None
    phone: str | None = None
    kyc_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Deposit (CASA) accounts -----------------------------------------------

class DepositAccountCreateRequest(BaseModel):
    cif_no: str = Field(..., min_length=1)
    account_type: AccountType = AccountType.SAVINGS


class DepositAccountStatusUpdateRequest(BaseModel):
    status: DepositAccountStatus


class DepositAccountResponse(BaseModel):
    account_no: str
    cif_no: str
    account_type: str
    currency: str
    balance: float
    status: str
    gl_code: str
    opened_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BalanceResponse(BaseModel):
    account_no: str
    currency: str
    balance: float
    status: str


# --- Loan accounts ----------------------------------------------------------

class LoanAccountCreateRequest(BaseModel):
    cif_no: str = Field(..., min_length=1)
    product_code: str = Field(..., min_length=1)
    los_application_id: str = Field(..., min_length=1)
    sanction_amount: float = Field(..., gt=0)
    interest_rate: float = Field(..., ge=0)
    tenure_months: int = Field(..., gt=0)
    emi_amount: float = Field(..., gt=0)
    disbursement_account_no: str = Field(..., min_length=1)


class LoanAccountResponse(BaseModel):
    loan_account_no: str
    cif_no: str
    product_code: str
    los_application_id: str
    sanction_amount: float
    interest_rate: float
    tenure_months: int
    emi_amount: float
    disbursement_account_no: str
    currency: str
    principal_outstanding: float
    installments_total: int
    installments_paid: int
    status: str
    disbursed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
