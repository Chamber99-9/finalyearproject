from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId

SCORING_MODEL_VERSION = "v1"
SCORE_TYPE = "rule_based_credit_risk_score"
RISK_SCORE_DISCLAIMER = (
    "This is a rule-based credit risk score for loan officer decision support only. "
    "It is not an official credit bureau score and must not be used for automatic "
    "loan approval or rejection."
)


class RiskLevel(StrEnum):
    LOW = "Low Credit Risk"
    MEDIUM = "Medium Credit Risk"
    HIGH = "High Credit Risk"


def create_risk_score_document(
    *,
    application_id: str,
    raw_score: int,
    normalized_score: int,
    risk_level: RiskLevel,
    dti_ratio: float,
    lti_ratio: float,
    score_breakdown: dict[str, int],
    repayment_history_used: str,
    repayment_history_score: int,
    monthly_emi: float = 0.0,
    affordability: str | None = None,
) -> dict[str, Any]:
    return {
        "application_id": application_id,
        "score_type": SCORE_TYPE,
        "raw_score": raw_score,
        "normalized_score": normalized_score,
        "risk_level": risk_level.value,
        "dti_ratio": dti_ratio,
        "lti_ratio": lti_ratio,
        # EMI used in the DTI, plus the affordability recommendation (req #8/#9).
        "monthly_emi": monthly_emi,
        "affordability": affordability,
        "score_breakdown": score_breakdown,
        "repayment_history_used": repayment_history_used,
        "repayment_history_score": repayment_history_score,
        "scoring_model_version": SCORING_MODEL_VERSION,
        "disclaimer": RISK_SCORE_DISCLAIMER,
        "created_at": datetime.now(UTC),
    }


def risk_score_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document
