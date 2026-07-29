from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_CORRECTED_DATA_KEYS = {
    "full_name",
    "monthly_income",
    "account_holder_name",
    "citizenship_number",
    "phone",
    "address",
    "employee_name",
    "employer_name",
    "bank_name",
    "account_number",
    "document_date",
}
MAX_CORRECTED_DATA_KEYS = 20
MAX_CORRECTED_STRING_LENGTH = 200


class OCRVerifyRequest(BaseModel):
    corrected_data: dict[str, Any]

    @field_validator("corrected_data")
    @classmethod
    def validate_corrected_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_CORRECTED_DATA_KEYS:
            raise ValueError("Corrected data contains too many fields")

        cleaned: dict[str, Any] = {}
        for key, field_value in value.items():
            key = str(key).strip()
            if key not in ALLOWED_CORRECTED_DATA_KEYS:
                raise ValueError(f"Unsupported corrected data field: {key}")

            if isinstance(field_value, str):
                field_value = field_value.strip()
                if len(field_value) > MAX_CORRECTED_STRING_LENGTH:
                    raise ValueError(f"Corrected data field is too long: {key}")
            elif field_value is not None and not isinstance(
                field_value,
                (int, float, bool),
            ):
                raise ValueError(f"Unsupported corrected data value for field: {key}")

            cleaned[key] = field_value

        return cleaned


class OCRResultResponse(BaseModel):
    id: str
    document_id: str
    application_id: str
    extracted_text: str
    confidence_score: float | None
    # Signature-based document-type detection.
    detected_document_type: str | None = None
    detected_label: str | None = None
    detection_confidence: float | None = None
    matched_keywords: list[str] = []
    detected_fields: dict[str, Any] = {}
    type_match: bool | None = None
    verified_by_user: bool
    corrected_data: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
