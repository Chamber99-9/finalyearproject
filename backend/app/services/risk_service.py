from math import isfinite
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.application import EmploymentType, RepaymentHistory, SavingsBuffer
from app.models.risk import (
    RISK_SCORE_DISCLAIMER,
    SCORE_TYPE,
    RiskLevel,
    create_risk_score_document,
    risk_score_id_to_str,
)
from app.services.emi_service import classify_affordability

CREDIT_RISK_SCORES_COLLECTION = "credit_risk_scores"
UNKNOWN_REPAYMENT_HISTORY = "unknown"


class RiskValidationError(Exception):
    pass


class RiskScoreStorageError(Exception):
    pass


def serialize_risk_score(document: dict[str, Any]) -> dict[str, Any]:
    return risk_score_id_to_str(document)


def _number_from_application(application: dict[str, Any], field_name: str) -> float:
    value = application.get(field_name)
    if isinstance(value, bool):
        raise RiskValidationError(f"{field_name} must be a number.")

    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise RiskValidationError(f"{field_name} must be a number.") from error

    if not isfinite(number):
        raise RiskValidationError(f"{field_name} must be a finite number.")
    return number


def _optional_number(
    application: dict[str, Any],
    field_name: str,
    default: float = 0.0,
) -> float:
    """Read a numeric field, returning ``default`` when it is missing/invalid.

    Used for ``monthly_emi`` so applications scored before EMI was stored still
    produce a valid (EMI-free) debt-to-income ratio instead of erroring.
    """
    value = application.get(field_name)
    if value is None or isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _dependents_from_application(application: dict[str, Any]) -> int:
    value = application.get("dependents")
    if isinstance(value, bool):
        raise RiskValidationError("dependents must be a number.")

    try:
        dependents = float(value)
    except (TypeError, ValueError) as error:
        raise RiskValidationError("dependents must be a number.") from error

    if not isfinite(dependents):
        raise RiskValidationError("dependents must be a finite number.")
    if not dependents.is_integer():
        raise RiskValidationError("dependents must be a whole number.")
    return int(dependents)


def _validate_enum_value(enum_class: type, value: Any, field_name: str) -> str:
    valid_values = {member.value for member in enum_class}
    if value not in valid_values:
        raise RiskValidationError(
            f"{field_name} must be one of: {', '.join(sorted(valid_values))}."
        )
    return str(value)


def _repayment_history_from_application(application: dict[str, Any]) -> str:
    value = application.get("repayment_history")
    if value is None:
        return UNKNOWN_REPAYMENT_HISTORY
    if isinstance(value, str) and not value.strip():
        return UNKNOWN_REPAYMENT_HISTORY

    return _validate_enum_value(RepaymentHistory, value, "repayment_history")


def _score_monthly_income(monthly_income: float) -> int:
    if monthly_income > 80000:
        return 15
    if monthly_income >= 50000:
        return 12
    if monthly_income >= 25000:
        return 8
    return 4


def _score_employment_stability(employment_type: str) -> int:
    scores = {
        EmploymentType.SALARIED.value: 15,
        EmploymentType.BUSINESS.value: 12,
        EmploymentType.SELF_EMPLOYED.value: 12,
        EmploymentType.CONTRACT.value: 6,
        EmploymentType.OTHER.value: 6,
        EmploymentType.UNEMPLOYED.value: 0,
    }
    return scores[employment_type]


def _score_dti_ratio(dti_ratio: float) -> int:
    if dti_ratio < 30:
        return 20
    if dti_ratio <= 50:
        return 10
    return 0


def _score_lti_ratio(lti_ratio: float) -> int:
    if lti_ratio < 10:
        return 15
    if lti_ratio <= 20:
        return 8
    return 0


def _score_repayment_history(repayment_history: str) -> int:
    scores = {
        RepaymentHistory.NO_PREVIOUS_DEFAULT.value: 20,
        RepaymentHistory.MINOR_LATE_PAYMENT.value: 10,
        RepaymentHistory.PREVIOUS_DEFAULT.value: 0,
        UNKNOWN_REPAYMENT_HISTORY: 12,
    }
    return scores[repayment_history]


def _score_dependents(dependents: int) -> int:
    if dependents <= 2:
        return 5
    if dependents <= 4:
        return 3
    return 0


def _score_savings_buffer(savings_buffer: str) -> int:
    scores = {
        SavingsBuffer.GOOD.value: 10,
        SavingsBuffer.AVERAGE.value: 6,
        SavingsBuffer.LOW.value: 0,
    }
    return scores[savings_buffer]


def classify_risk(normalized_score: int) -> RiskLevel:
    if normalized_score >= 700:
        return RiskLevel.LOW
    if normalized_score >= 550:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def calculate_credit_risk(application: dict[str, Any]) -> dict[str, Any]:
    monthly_income = _number_from_application(application, "monthly_income")
    existing_monthly_debt = _number_from_application(
        application,
        "existing_monthly_debt",
    )
    requested_loan_amount = _number_from_application(
        application,
        "requested_loan_amount",
    )
    dependents = _dependents_from_application(application)
    employment_type = _validate_enum_value(
        EmploymentType,
        application.get("employment_type"),
        "employment_type",
    )
    repayment_history = _repayment_history_from_application(application)
    savings_buffer = _validate_enum_value(
        SavingsBuffer,
        application.get("savings_buffer"),
        "savings_buffer",
    )

    if monthly_income <= 0:
        raise RiskValidationError("monthly_income must be greater than 0.")
    if existing_monthly_debt < 0:
        raise RiskValidationError("existing_monthly_debt must not be negative.")
    if requested_loan_amount <= 0:
        raise RiskValidationError("requested_loan_amount must be greater than 0.")
    if dependents < 0:
        raise RiskValidationError("dependents must not be negative.")

    # Debt-to-income now includes the calculated EMI for this loan (requirement
    # #8): DTI = (existing_monthly_debt + monthly_emi) / monthly_income * 100.
    # ``monthly_emi`` is stored on the application when loan details are saved.
    monthly_emi = _optional_number(application, "monthly_emi", 0.0)
    dti_ratio = round(
        ((existing_monthly_debt + monthly_emi) / monthly_income) * 100,
        2,
    )
    lti_ratio = round(requested_loan_amount / monthly_income, 2)

    # Affordability recommendation derived from the EMI-inclusive DTI (req #9).
    affordability = classify_affordability(dti_ratio)

    repayment_history_score = _score_repayment_history(repayment_history)
    score_breakdown = {
        "monthly_income_score": _score_monthly_income(monthly_income),
        "employment_stability_score": _score_employment_stability(employment_type),
        "dti_score": _score_dti_ratio(dti_ratio),
        "lti_score": _score_lti_ratio(lti_ratio),
        "repayment_history_score": repayment_history_score,
        "dependents_score": _score_dependents(dependents),
        "savings_buffer_score": _score_savings_buffer(savings_buffer),
    }
    raw_score = sum(score_breakdown.values())
    normalized_score = round(300 + (raw_score / 100) * 550)

    return {
        "score_type": SCORE_TYPE,
        "raw_score": raw_score,
        "normalized_score": normalized_score,
        "risk_level": classify_risk(normalized_score),
        "dti_ratio": dti_ratio,
        "lti_ratio": lti_ratio,
        "monthly_emi": monthly_emi,
        "affordability": affordability,
        "score_breakdown": score_breakdown,
        "repayment_history_used": repayment_history,
        "repayment_history_score": repayment_history_score,
        "disclaimer": RISK_SCORE_DISCLAIMER,
    }


async def calculate_and_save_credit_risk(
    database: AsyncIOMotorDatabase,
    application: dict[str, Any],
) -> dict[str, Any]:
    calculation = calculate_credit_risk(application)
    document = create_risk_score_document(
        application_id=str(application["_id"]),
        raw_score=calculation["raw_score"],
        normalized_score=calculation["normalized_score"],
        risk_level=calculation["risk_level"],
        dti_ratio=calculation["dti_ratio"],
        lti_ratio=calculation["lti_ratio"],
        monthly_emi=calculation["monthly_emi"],
        affordability=calculation["affordability"],
        score_breakdown=calculation["score_breakdown"],
        repayment_history_used=calculation["repayment_history_used"],
        repayment_history_score=calculation["repayment_history_score"],
    )

    try:
        result = await database[CREDIT_RISK_SCORES_COLLECTION].insert_one(document)
    except Exception as error:
        raise RiskScoreStorageError from error

    document["_id"] = result.inserted_id
    return document


async def get_latest_risk_score_for_application(
    database: AsyncIOMotorDatabase,
    application_id: str,
) -> dict[str, Any] | None:
    return await database[CREDIT_RISK_SCORES_COLLECTION].find_one(
        {"application_id": application_id},
        sort=[("created_at", -1)],
    )
