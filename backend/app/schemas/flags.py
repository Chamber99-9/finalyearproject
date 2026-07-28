from pydantic import BaseModel, ConfigDict

from app.models.flags import FlagCode, FlagSeverity, SuspicionLevel


class SuspiciousFlagResponseItem(BaseModel):
    code: FlagCode
    message: str
    severity: FlagSeverity


class ApplicationFlagsResponse(BaseModel):
    application_id: str
    total_flags: int
    suspicion_level: SuspicionLevel
    flags: list[SuspiciousFlagResponseItem]

    model_config = ConfigDict(from_attributes=True)
