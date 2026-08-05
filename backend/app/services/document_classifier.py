"""Signature-based classifier for Nepali KYC documents.

Given the OCR-extracted text of an uploaded document, detect what kind of
document it is — citizenship certificate, PAN, bank statement, salary/offer
letter, land valuation report, or recommendation letter — by matching the text
against a *signature* of each type: characteristic keywords (English and Nepali)
plus ID-number patterns. It returns the best-matching type, a confidence score
(the share of that type's signature that is present), the keywords that matched,
and any fields it could pull out.

This is deterministic signature detection, not machine learning — the same
approach real KYC pipelines use for a first-pass document check. An officer
still confirms the result; a low confidence or a mismatch against the type the
customer said they were uploading is surfaced as a warning rather than a block.
"""

from __future__ import annotations

import re
from typing import Any

# --- Document classes -------------------------------------------------------
CITIZENSHIP = "citizenship"
PAN = "pan"
BANK_STATEMENT = "bank_statement"
SALARY_OR_OFFER = "salary_or_offer"
VALUATION_REPORT = "valuation_report"
PROPERTY_PAPERS = "property_papers"
RECOMMENDATION_LETTER = "recommendation_letter"
OFFICIAL_DOCUMENT = "official_document"
UNKNOWN = "unknown"

HUMAN_LABEL: dict[str, str] = {
    CITIZENSHIP: "Citizenship certificate",
    PAN: "PAN (Permanent Account Number)",
    BANK_STATEMENT: "Bank statement",
    SALARY_OR_OFFER: "Salary / offer letter",
    VALUATION_REPORT: "Land / property valuation report",
    PROPERTY_PAPERS: "Property papers (land ownership certificate)",
    RECOMMENDATION_LETTER: "Recommendation letter",
    OFFICIAL_DOCUMENT: "Official / government document",
    UNKNOWN: "Unrecognised document",
}

# Maps the app's uploaded DocumentType -> the class we expect the text to match.
# ``None`` means "any content is acceptable for this upload slot".
DOCUMENT_TYPE_TO_CLASS: dict[str, str | None] = {
    "citizenship_document": CITIZENSHIP,
    "salary_slip": SALARY_OR_OFFER,
    "bank_statement": BANK_STATEMENT,
    "valuation_report": VALUATION_REPORT,
    "property_papers": PROPERTY_PAPERS,
    "recommendation_letter": RECOMMENDATION_LETTER,
    "supporting_document": None,
}

# --- Signatures: (keyword, weight). Strong/unique markers weigh more. --------
# Keywords are matched as lowercase substrings, so Nepali (Devanagari) terms
# work unchanged. Weight 3+ = decisive, 2 = strong, 1 = supporting.
SIGNATURES: dict[str, list[tuple[str, float]]] = {
    CITIZENSHIP: [
        ("citizenship certificate", 3.0),
        ("certificate of citizenship", 3.0),
        ("नागरिकताको प्रमाणपत्र", 3.0),
        ("नागरिकता प्रमाणपत्र", 3.0),
        ("नागरिकता", 2.5),
        ("citizenship no", 2.5),
        ("citizenship number", 2.5),
        ("नागरिकता नं", 2.5),
        ("ministry of home affairs", 2.0),
        ("गृह मन्त्रालय", 2.0),
        ("district administration office", 2.0),
        ("जिल्ला प्रशासन कार्यालय", 2.0),
        ("government of nepal", 1.5),
        ("नेपाल सरकार", 1.5),
        ("place of birth", 1.0),
        ("permanent resident", 1.0),
    ],
    PAN: [
        ("permanent account number", 3.5),
        ("स्थायी लेखा नम्बर", 3.5),
        ("inland revenue department", 3.0),
        ("आन्तरिक राजस्व विभाग", 3.0),
        ("pan number", 2.5),
        ("pan no", 2.5),
        ("taxpayer", 1.5),
        ("करदाता", 1.5),
        ("tax registration", 1.5),
        ("value added tax", 1.0),
        (" pan ", 1.5),
    ],
    BANK_STATEMENT: [
        ("statement of account", 3.0),
        ("account statement", 3.0),
        ("bank statement", 3.0),
        ("opening balance", 2.5),
        ("closing balance", 2.5),
        ("available balance", 2.0),
        ("ledger balance", 2.0),
        ("value date", 1.5),
        ("account number", 1.5),
        ("a/c no", 1.5),
        ("transaction", 1.0),
        ("withdrawal", 1.0),
        ("deposit", 1.0),
        # Nepali commercial banks
        ("nabil bank", 2.0),
        ("nic asia", 2.0),
        ("global ime", 2.0),
        ("nmb bank", 2.0),
        ("siddhartha bank", 2.0),
        ("standard chartered", 2.0),
        ("rastriya banijya", 2.0),
        ("nepal bank", 2.0),
        ("prabhu bank", 2.0),
        ("kumari bank", 2.0),
        ("machhapuchhre", 2.0),
        ("sanima bank", 2.0),
        ("everest bank", 2.0),
        ("himalayan bank", 2.0),
        ("citizens bank", 2.0),
        ("sunrise bank", 2.0),
        ("prime commercial", 2.0),
        ("laxmi", 1.5),
    ],
    SALARY_OR_OFFER: [
        ("offer letter", 3.0),
        ("appointment letter", 3.0),
        ("letter of appointment", 3.0),
        ("salary certificate", 3.0),
        ("salary slip", 3.0),
        ("pay slip", 3.0),
        ("payslip", 3.0),
        ("we are pleased to offer", 3.0),
        ("pleased to offer you", 3.0),
        ("gross salary", 2.5),
        ("net salary", 2.5),
        ("basic salary", 2.5),
        ("monthly salary", 2.0),
        ("annual salary", 2.0),
        ("cost to company", 2.0),
        ("date of joining", 2.0),
        ("designation", 1.5),
        ("remuneration", 1.5),
        ("ctc", 1.5),
        ("per month", 1.0),
        ("per annum", 1.0),
        ("employer", 1.0),
        ("employee", 1.0),
    ],
    VALUATION_REPORT: [
        ("valuation report", 3.0),
        ("valuation of", 2.5),
        ("fair market value", 2.5),
        ("market value", 2.0),
        ("distress value", 2.0),
        ("valuator", 2.0),
        ("valuer", 2.0),
        ("engineer", 1.0),
        ("plot no", 1.5),
        ("kitta no", 2.0),
        ("kitta", 1.5),
        ("ropani", 2.0),
        ("aana", 1.5),
        ("plotting", 1.0),
        ("land revenue", 1.5),
        ("property", 1.0),
    ],
    RECOMMENDATION_LETTER: [
        ("recommendation letter", 3.0),
        ("letter of recommendation", 3.0),
        ("to whom it may concern", 2.5),
        ("hereby recommend", 2.5),
        ("we recommend", 2.0),
        ("i recommend", 2.0),
        ("ward office", 1.5),
        ("municipality", 1.0),
        ("recommend", 1.0),
        ("recommended", 1.0),
    ],
    PROPERTY_PAPERS: [
        ("land ownership certificate", 3.5),
        ("ownership certificate", 2.5),
        ("जग्गा धनी प्रमाण पुर्जा", 3.5),
        ("जग्गा धनी", 3.0),
        ("लालपुर्जा", 3.5),
        ("lalpurja", 3.0),
        ("land revenue office", 2.5),
        ("malpot", 2.5),
        ("मालपोत", 2.5),
        ("parcel", 1.5),
        ("plot no", 1.5),
        ("kitta no", 1.5),
        ("kitta", 1.0),
        ("ropani", 1.0),
        ("aana", 1.0),
        ("registration no", 1.0),
    ],
    OFFICIAL_DOCUMENT: [
        ("patra sankhya", 3.0),
        ("पत्र संख्या", 3.0),
        ("chalani", 2.5),
        ("चलानी", 2.5),
        ("to whom it may concern", 2.0),
        ("office of the", 2.0),
        ("ref no", 1.5),
        ("reference no", 1.5),
        ("subject:", 1.5),
        ("विषय", 1.5),
        ("official seal", 2.0),
        ("nagarpalika", 1.5),
        ("gaunpalika", 1.5),
        ("ward office", 1.5),
        ("ministry of", 1.5),
        ("मन्त्रालय", 1.5),
        ("कार्यालय", 1.5),
        ("government of nepal", 1.0),
        ("नेपाल सरकार", 1.0),
    ],
}

# Confidence = min(0.99, score / SATURATION). SATURATION is the score at which
# we're effectively certain (roughly one decisive marker + one strong marker).
SATURATION = 5.0
# Below this best score, the document is treated as unrecognised.
MIN_SCORE = 2.0

_PAN_RE = re.compile(r"(?<!\d)(\d{9})(?!\d)")
_AMOUNT = r"(?:npr|nrs\.?|rs\.?|रु\.?)?\s*([\d,]{4,}(?:\.\d{1,2})?)"


def _score_type(lowered: str, signature: list[tuple[str, float]]) -> tuple[float, list[str]]:
    score = 0.0
    hits: list[str] = []
    for keyword, weight in signature:
        if keyword in lowered:
            score += weight
            hits.append(keyword.strip())
    return round(score, 2), hits


def _value_after(text: str, labels: list[str], pattern: str) -> str | None:
    """Find the first ``pattern`` match that appears shortly after any label."""
    for label in labels:
        match = re.search(re.escape(label) + r"[^0-9A-Za-zऀ-ॿ]{0,20}?(" + pattern + r")", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


_NAME_STOPWORDS = {
    "date", "sex", "birth", "place", "citizenship", "address", "district",
    "month", "day", "year", "permanent", "of", "and", "the", "certificate",
    "male", "female", "father", "mother", "spouse",
}


def _clean_person_name(name: str | None) -> str | None:
    """Trim trailing non-name words that OCR often runs into a name."""
    if not name:
        return None
    tokens: list[str] = []
    for token in name.split():
        if token.lower() in _NAME_STOPWORDS:
            break
        tokens.append(token)
        if len(tokens) >= 4:
            break
    cleaned = " ".join(tokens).strip()
    return cleaned or None


def _citizenship_address(text: str) -> str | None:
    """Best-effort permanent address from a citizenship certificate.

    Composes municipality + ward + district. The district lookup skips the
    "District Administration Office" header so it picks the resident district.
    """
    municipality = _value_after(
        text, ["municipality", "nagarpalika", "gaunpalika", "vdc", "न पा"], r"[A-Za-zऀ-ॿ]{3,}"
    )
    ward = _value_after(text, ["ward no", "ward", "वडा"], r"\d{1,2}")
    district = None
    for match in re.finditer(r"district[^0-9A-Za-zऀ-ॿ]{0,10}([A-Za-zऀ-ॿ]{3,})", text, re.IGNORECASE):
        candidate = match.group(1)
        if candidate.lower() not in {"administration", "admin", "prashasan"}:
            district = candidate
            break
    parts = [part for part in [municipality, f"Ward {ward}" if ward else None, district] if part]
    return ", ".join(parts) if parts else None


def _extract_fields(text: str, doc_type: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    name = _clean_person_name(
        _value_after(text, ["full name", "name", "नाम"], r"[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,3}")
    )
    if name:
        fields["name"] = name

    if doc_type == PAN:
        pan = _value_after(text, ["permanent account number", "pan number", "pan no", "pan"], r"\d{9}")
        if not pan:
            found = _PAN_RE.search(text)
            pan = found.group(1) if found else None
        if pan:
            fields["pan_number"] = pan
    elif doc_type == CITIZENSHIP:
        cit = _value_after(
            text,
            ["citizenship certificate no", "citizenship number", "citizenship no", "नागरिकता नं"],
            r"\d[\d\-/]{4,}",
        )
        if cit:
            fields["citizenship_number"] = cit
        address = _citizenship_address(text)
        if address:
            fields["address"] = address
    elif doc_type == BANK_STATEMENT:
        acc = _value_after(text, ["account number", "a/c no", "account no"], r"\d[\d\-]{5,}")
        if acc:
            fields["account_number"] = acc
        bal = _value_after(text, ["closing balance", "available balance", "ledger balance", "balance"], _AMOUNT)
        if bal:
            fields["balance"] = bal
    elif doc_type == SALARY_OR_OFFER:
        salary = _value_after(
            text,
            ["gross salary", "net salary", "monthly salary", "basic salary", "salary", "remuneration"],
            _AMOUNT,
        )
        if salary:
            fields["salary"] = salary
    elif doc_type == VALUATION_REPORT:
        value = _value_after(text, ["fair market value", "market value", "distress value", "valuation"], _AMOUNT)
        if value:
            fields["valuation_amount"] = value
    elif doc_type == PROPERTY_PAPERS:
        kitta = _value_after(text, ["kitta no", "kitta", "plot no", "parcel no"], r"\d[\d\-/]{0,12}")
        if kitta:
            fields["kitta_number"] = kitta
    return fields


def classify_document(text: str, *, expected_document_type: str | None = None) -> dict[str, Any]:
    """Detect the document type of ``text``.

    ``expected_document_type`` is the app's ``DocumentType`` the customer chose
    for this upload (e.g. ``"citizenship_document"``). When given, the result
    includes ``type_match`` (True/False/None) so the UI can flag a mismatch such
    as a PAN card uploaded into the citizenship slot.
    """
    raw = text or ""
    lowered = " " + re.sub(r"\s+", " ", raw.lower()) + " "

    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for doc_type, signature in SIGNATURES.items():
        score, hits = _score_type(lowered, signature)
        scores[doc_type] = score
        matched[doc_type] = hits

    # A well-formed 9-digit number reinforces a PAN reading (but only if there
    # is already some PAN keyword signal, to avoid false positives on any ID).
    if scores[PAN] > 0 and _PAN_RE.search(raw):
        scores[PAN] = round(scores[PAN] + 1.0, 2)

    best_type = max(scores, key=lambda key: scores[key])
    best_score = scores[best_type]
    ranked = sorted(scores.values(), reverse=True)
    runner_up = ranked[1] if len(ranked) > 1 else 0.0

    if best_score < MIN_SCORE:
        detected = UNKNOWN
        confidence = round(min(0.4, best_score / SATURATION), 2)
        fields: dict[str, str] = {}
        keywords: list[str] = []
    else:
        detected = best_type
        confidence = round(min(0.99, best_score / SATURATION), 2)
        fields = _extract_fields(raw, detected)
        keywords = matched[detected]

    expected_class = None
    type_match: bool | None = None
    if expected_document_type is not None:
        expected_class = DOCUMENT_TYPE_TO_CLASS.get(expected_document_type, expected_document_type)
        if expected_class is None:  # "supporting_document" — anything goes
            type_match = True
        elif detected == UNKNOWN:
            type_match = None  # couldn't tell; officer decides
        else:
            type_match = detected == expected_class

    return {
        "detected_document_type": detected,
        "detected_label": HUMAN_LABEL[detected],
        "confidence": confidence,
        "matched_keywords": keywords,
        "detected_fields": fields,
        "scores": {key: scores[key] for key in scores},
        "margin": round(best_score - runner_up, 2),
        "expected_document_type": expected_document_type,
        "expected_class": expected_class,
        "type_match": type_match,
    }
