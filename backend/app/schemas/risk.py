from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.risk import RiskLevel


class CreditRiskResponse(BaseModel):
    application_id: str
    score_type: str
    raw_score: int
    normalized_score: int
    risk_level: RiskLevel
    dti_ratio: float
    lti_ratio: float
    monthly_emi: float = 0.0
    affordability: str | None = None
    score_breakdown: dict[str, int]
    repayment_history_used: str
    repayment_history_score: int
    scoring_model_version: str
    disclaimer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
