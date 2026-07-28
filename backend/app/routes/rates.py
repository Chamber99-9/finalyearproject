"""Loan rate menu + quote routes.

    GET  /loan-rates/types  -> loan products with this-month indicative rates
    POST /loan-rates/quote  -> effective rate for a loan type + tenure
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_current_user
from app.database import get_database
from app.schemas.rates import (
    LoanRateQuoteRequest,
    LoanRateQuoteResponse,
    LoanTypeInfoResponse,
)
from app.services.emi_service import normalize_tenure_to_months
from app.services.loan_rate_service import (
    LOAN_TYPE_INFO,
    compute_effective_rate,
    get_type_spread,
)
from app.services.loan_settings_service import get_base_lending_rate

router = APIRouter(prefix="/loan-rates", tags=["loan-rates"])


@router.get("/types", response_model=list[LoanTypeInfoResponse])
async def read_loan_types(
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> list[dict]:
    """List loan products with an indicative rate (base + type spread) for today.

    The indicative rate excludes the tenure adjustment; the exact rate is
    returned by /loan-rates/quote once the customer picks a tenure.
    """
    base_rate = await get_base_lending_rate(database)
    result: list[dict] = []
    for info in LOAN_TYPE_INFO:
        spread = get_type_spread(info["loan_type"])
        result.append(
            {
                **info,
                "base_rate": round(base_rate, 2),
                "type_spread": spread,
                "indicative_rate": round(base_rate + spread, 2),
            }
        )
    return result


@router.post("/quote", response_model=LoanRateQuoteResponse)
async def quote_rate(
    payload: LoanRateQuoteRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    """Return the effective rate for a loan type + tenure."""
    tenure_months = normalize_tenure_to_months(payload.tenure, payload.tenure_unit)
    return await compute_effective_rate(database, payload.loan_type, tenure_months)
