from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentType


class DocumentResponse(BaseModel):
    id: str
    application_id: str
    user_id: str
    document_type: DocumentType
    filename: str
    content_type: str
    uploaded_at: datetime
    # Auto-detected on upload (used to prefill the application form).
    detected_citizenship_number: str | None = None
    detected_name: str | None = None

    model_config = ConfigDict(from_attributes=True)
