"""Loan account routes: customer payments + admin maintenance jobs.

    GET  /loans/my                       -> customer's loan accounts
    POST /loans/{loan_id}/pay            -> pay one EMI (reduces balance)
    POST /loans/maintenance/reminders    -> send 2-day due reminders (admin)
    POST /loans/maintenance/overdue      -> advance overdue + blacklist (admin)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_authenticated_user_id, require_admin, require_customer
from app.database import get_database
from app.schemas.loans import (
    LoanAccountResponse,
    OverdueResponse,
    PaymentResponse,
    RemindersResponse,
)
from app.services.loan_account_service import (
    LoanAccountNotFoundError,
    LoanAccountStatusError,
    list_customer_loans,
    process_due_reminders,
    process_overdue,
    record_payment,
    serialize_loan_account,
)

router = APIRouter(prefix="/loans", tags=["loans"])


@router.get("/my", response_model=list[LoanAccountResponse])
async def read_my_loans(
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    applicant_id = get_authenticated_user_id(current_user)
    loans = await list_customer_loans(database, applicant_id)
    return [serialize_loan_account(loan) for loan in loans]


@router.post("/{loan_id}/pay", response_model=PaymentResponse)
async def pay_emi(
    loan_id: str,
    current_user: Annotated[dict, Depends(require_customer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    applicant_id = get_authenticated_user_id(current_user)
    try:
        loan = await record_payment(database, loan_id, applicant_id)
    except LoanAccountNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan account not found.",
        ) from error
    except LoanAccountStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This loan is not active; no payment is due.",
        ) from error

    amount_paid = loan.pop("_last_payment", 0.0)
    return {"amount_paid": amount_paid, "loan": serialize_loan_account(loan)}


@router.post("/maintenance/reminders", response_model=RemindersResponse)
async def run_due_reminders(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Send 'EMI due in 2 days' notifications + emails (run by a scheduler)."""
    return await process_due_reminders(database)


@router.post("/maintenance/overdue", response_model=OverdueResponse)
async def run_overdue_check(
    current_user: Annotated[dict, Depends(require_admin)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Advance overdue loans and blacklist repeat defaulters (run by a scheduler)."""
    return await process_overdue(database)
