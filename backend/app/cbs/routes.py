"""CBS API — Customer Account and Loan Account modules.

Mounted under ``/cbs/v1``. These are bank-internal operations, so every endpoint
requires an officer or admin. The CBS is a separate bounded context: it never
touches the LOS collections directly, only references them by id.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import require_officer_or_admin
from app.cbs.schemas import (
    BalanceResponse,
    CifCreateRequest,
    CifResponse,
    DepositAccountCreateRequest,
    DepositAccountResponse,
    DepositAccountStatusUpdateRequest,
    LoanAccountCreateRequest,
    LoanAccountResponse,
)
from app.cbs.services import accounts as accounts_service
from app.cbs.services import cif as cif_service
from app.cbs.services import loans as loans_service
from app.database import get_database

router = APIRouter(
    prefix="/cbs/v1",
    tags=["cbs"],
    dependencies=[Depends(require_officer_or_admin)],
)

DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


# --- CIF (customer master) --------------------------------------------------

@router.post("/cif", response_model=CifResponse, status_code=status.HTTP_201_CREATED)
async def create_cif(payload: CifCreateRequest, database: DatabaseDep) -> CifResponse:
    document = await cif_service.create_or_get_cif(
        database,
        los_user_id=payload.los_user_id,
        full_name=payload.full_name,
        citizenship_no=payload.citizenship_no,
        pan=payload.pan,
        phone=payload.phone,
        kyc_status=payload.kyc_status,
    )
    return CifResponse(**cif_service.serialize_cif(document))


@router.get("/cif/{cif_no}", response_model=CifResponse)
async def get_cif(cif_no: str, database: DatabaseDep) -> CifResponse:
    try:
        document = await cif_service.get_cif(database, cif_no)
    except cif_service.CifNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CIF not found")
    return CifResponse(**cif_service.serialize_cif(document))


# --- Deposit (CASA) accounts -----------------------------------------------

@router.post(
    "/deposit-accounts",
    response_model=DepositAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def open_deposit_account(
    payload: DepositAccountCreateRequest, database: DatabaseDep
) -> DepositAccountResponse:
    try:
        document = await accounts_service.open_deposit_account(
            database,
            cif_no=payload.cif_no,
            account_type=payload.account_type.value,
        )
    except accounts_service.CifRequiredError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CIF not found")
    return DepositAccountResponse(**accounts_service.serialize_deposit_account(document))


@router.get("/deposit-accounts/{account_no}", response_model=DepositAccountResponse)
async def get_deposit_account(account_no: str, database: DatabaseDep) -> DepositAccountResponse:
    try:
        document = await accounts_service.get_deposit_account(database, account_no)
    except accounts_service.DepositAccountNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return DepositAccountResponse(**accounts_service.serialize_deposit_account(document))


@router.get("/deposit-accounts/{account_no}/balance", response_model=BalanceResponse)
async def get_deposit_balance(account_no: str, database: DatabaseDep) -> BalanceResponse:
    try:
        document = await accounts_service.get_deposit_account(database, account_no)
    except accounts_service.DepositAccountNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return BalanceResponse(
        account_no=document["account_no"],
        currency=document["currency"],
        balance=float(document.get("balance") or 0),
        status=document["status"],
    )


@router.patch("/deposit-accounts/{account_no}/status", response_model=DepositAccountResponse)
async def update_deposit_status(
    account_no: str,
    payload: DepositAccountStatusUpdateRequest,
    database: DatabaseDep,
) -> DepositAccountResponse:
    try:
        document = await accounts_service.set_account_status(
            database, account_no, payload.status
        )
    except accounts_service.DepositAccountNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    except accounts_service.DepositAccountStateError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Account with a non-zero balance cannot be closed"
        )
    return DepositAccountResponse(**accounts_service.serialize_deposit_account(document))


# --- Loan accounts ----------------------------------------------------------

@router.post(
    "/loans",
    response_model=LoanAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def open_loan_account(
    payload: LoanAccountCreateRequest, database: DatabaseDep
) -> LoanAccountResponse:
    try:
        document = await loans_service.open_loan_account(
            database,
            cif_no=payload.cif_no,
            product_code=payload.product_code,
            los_application_id=payload.los_application_id,
            sanction_amount=payload.sanction_amount,
            interest_rate=payload.interest_rate,
            tenure_months=payload.tenure_months,
            emi_amount=payload.emi_amount,
            disbursement_account_no=payload.disbursement_account_no,
        )
    except loans_service.LoanTermsError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid loan terms")
    except loans_service.CifRequiredError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CIF not found")
    except loans_service.DisbursementAccountRequiredError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Disbursement account not found for this CIF",
        )
    return LoanAccountResponse(**loans_service.serialize_loan_account(document))


@router.get("/loans/{loan_account_no}", response_model=LoanAccountResponse)
async def get_loan_account(loan_account_no: str, database: DatabaseDep) -> LoanAccountResponse:
    try:
        document = await loans_service.get_loan_account(database, loan_account_no)
    except loans_service.LoanAccountNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan account not found")
    return LoanAccountResponse(**loans_service.serialize_loan_account(document))
