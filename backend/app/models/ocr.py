from datetime import UTC, datetime
from typing import Any

from bson import ObjectId


def create_ocr_result_document(
    *,
    document_id: str,
    application_id: str,
    extracted_text: str,
    confidence_score: float | None,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "application_id": application_id,
        "extracted_text": extracted_text,
        "confidence_score": confidence_score,
        # Signature-based document-type detection (see document_classifier).
        "detected_document_type": (classification or {}).get("detected_document_type"),
        "detected_label": (classification or {}).get("detected_label"),
        "detection_confidence": (classification or {}).get("confidence"),
        "matched_keywords": (classification or {}).get("matched_keywords", []),
        "detected_fields": (classification or {}).get("detected_fields", {}),
        "type_match": (classification or {}).get("type_match"),
        "verified_by_user": False,
        "corrected_data": {},
        "created_at": datetime.now(UTC),
    }


def ocr_result_id_to_str(document: dict[str, Any]) -> dict[str, Any]:
    document = document.copy()
    if isinstance(document.get("_id"), ObjectId):
        document["id"] = str(document.pop("_id"))
    return document

