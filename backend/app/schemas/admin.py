from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserRoleUpdateRequest(BaseModel):
    role: UserRole


class AdminOverviewResponse(BaseModel):
    total_users: int
    total_applications: int
    pending_applications: int


class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
