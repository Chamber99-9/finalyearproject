"""At-upload document verification.

For the three required KYC documents (citizenship, salary slip, bank statement),
the uploaded file is read (image or PDF) and matched against the type the
customer said they were sending. A match is accepted; a wrong or unrecognisable
document is rejected so the customer re-sends the correct one.

Other document types (collateral valuation, property papers, supporting) are not
hard-gated here — they are still classified for the officer's hint.
"""

from typing import Any

from app.services.document_classifier import classify_document

# Documents that must be verified at upload time.
GATED_DOCUMENT_TYPES = {"citizenship_document", "salary_slip", "bank_statement"}
# Minimum detection confidence to accept a gated document.
ACCEPT_MIN_CONFIDENCE = 0.5


def verify_document_type(
    text: str,
    document_type: str,
    *,
    engine_available: bool,
) -> dict[str, Any]:
    """Decide whether an uploaded document is accepted.

    Returns ``{accepted, reason, classification}``.
    """
    classification = classify_document(text or "", expected_document_type=document_type)

    if document_type not in GATED_DOCUMENT_TYPES:
        return {
            "accepted": True,
            "reason": "Document uploaded.",
            "classification": classification,
        }

    if not engine_available:
        # We couldn't run the automatic check (OCR engine unavailable) — accept
        # and leave it to the officer rather than penalise the customer.
        return {
            "accepted": True,
            "reason": "Document uploaded (automatic check unavailable; an officer will verify).",
            "classification": classification,
        }

    confidence = classification.get("confidence") or 0
    if classification.get("type_match") is True and confidence >= ACCEPT_MIN_CONFIDENCE:
        return {
            "accepted": True,
            "reason": f"Your document is accepted — detected {classification['detected_label']}.",
            "classification": classification,
        }

    if classification.get("type_match") is False:
        return {
            "accepted": False,
            "reason": (
                f"This looks like a {classification['detected_label']}, not the requested "
                "document. Please send the correct document again."
            ),
            "classification": classification,
        }

    return {
        "accepted": False,
        "reason": (
            "We couldn't recognise this document. Please send a clearer image or PDF "
            "of the correct document again."
        ),
        "classification": classification,
    }
