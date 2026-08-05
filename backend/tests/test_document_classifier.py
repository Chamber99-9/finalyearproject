"""Tests for the signature-based document classifier.

Each sample below is representative OCR text (single-line, as Tesseract emits it
after word-joining) for a Nepali KYC document. We assert the detector picks the
right class, is confident, and flags a mismatch when the wrong document lands in
a slot.
"""

from app.services.document_classifier import (
    BANK_STATEMENT,
    CITIZENSHIP,
    OFFICIAL_DOCUMENT,
    PAN,
    PROPERTY_PAPERS,
    SALARY_OR_OFFER,
    UNKNOWN,
    classify_document,
)

CITIZENSHIP_TEXT = (
    "Government of Nepal Ministry of Home Affairs District Administration Office "
    "Citizenship Certificate नागरिकताको प्रमाणपत्र Full Name Ram Bahadur Thapa "
    "Citizenship No 12-01-75-04321 Place of Birth Kaski Permanent Resident"
)

PAN_TEXT = (
    "Government of Nepal Inland Revenue Department Permanent Account Number "
    "स्थायी लेखा नम्बर PAN No 301245987 Taxpayer Name Sita Kumari Shrestha "
    "Tax Registration Certificate"
)

BANK_TEXT = (
    "NABIL Bank Limited Statement of Account Account Number 0123456789012 "
    "Value Date Description Debit Credit Balance Opening Balance 45,000.00 "
    "Closing Balance 128,540.50 Available Balance 128,540.50"
)

SALARY_TEXT = (
    "ABC Technologies Pvt. Ltd. Offer Letter We are pleased to offer you the "
    "position of Software Engineer Designation Software Engineer Gross Salary "
    "NPR 85,000 per month Date of Joining 2081-04-01 Remuneration"
)


def test_detects_citizenship():
    result = classify_document(CITIZENSHIP_TEXT, expected_document_type="citizenship_document")
    assert result["detected_document_type"] == CITIZENSHIP
    assert result["confidence"] >= 0.8
    assert result["type_match"] is True
    assert result["detected_fields"].get("citizenship_number") == "12-01-75-04321"


def test_detects_pan():
    result = classify_document(PAN_TEXT, expected_document_type="supporting_document")
    assert result["detected_document_type"] == PAN
    assert result["confidence"] >= 0.8
    assert result["detected_fields"].get("pan_number") == "301245987"
    # supporting_document accepts anything
    assert result["type_match"] is True


def test_detects_bank_statement():
    result = classify_document(BANK_TEXT, expected_document_type="bank_statement")
    assert result["detected_document_type"] == BANK_STATEMENT
    assert result["confidence"] >= 0.8
    assert result["type_match"] is True
    assert result["detected_fields"].get("account_number") == "0123456789012"


def test_detects_salary_offer():
    result = classify_document(SALARY_TEXT, expected_document_type="salary_slip")
    assert result["detected_document_type"] == SALARY_OR_OFFER
    assert result["confidence"] >= 0.8
    assert result["type_match"] is True


def test_flags_type_mismatch():
    # Customer uploaded a PAN into the citizenship slot -> mismatch.
    result = classify_document(PAN_TEXT, expected_document_type="citizenship_document")
    assert result["detected_document_type"] == PAN
    assert result["type_match"] is False


def test_unknown_document_is_low_confidence():
    result = classify_document("hello world this is just some random text", expected_document_type=None)
    assert result["detected_document_type"] == UNKNOWN
    assert result["confidence"] < 0.5
    assert result["type_match"] is None


def test_pan_needs_keyword_not_just_digits():
    # Nine digits alone (no PAN wording) must not be classified as PAN.
    result = classify_document("random reference 123456789 with no other markers")
    assert result["detected_document_type"] != PAN


PROPERTY_TEXT = (
    "Government of Nepal Land Revenue Office Malpot Karyalaya Land Ownership Certificate "
    "जग्गा धनी प्रमाण पुर्जा लालपुर्जा Owner Ram Bahadur Thapa Kitta No 245 Area 0-4-2-0 Ropani"
)

OFFICIAL_TEXT = (
    "Government of Nepal Office of the Municipality Ref No 079/80-1421 Patra Sankhya "
    "Chalani No 552 Subject: Verification To whom it may concern this is to certify "
    "Official Seal Ward Office"
)


def test_detects_property_papers():
    result = classify_document(PROPERTY_TEXT, expected_document_type="property_papers")
    assert result["detected_document_type"] == PROPERTY_PAPERS
    assert result["confidence"] >= 0.8
    assert result["type_match"] is True


def test_detects_official_document():
    result = classify_document(OFFICIAL_TEXT)
    assert result["detected_document_type"] == OFFICIAL_DOCUMENT
    assert result["confidence"] >= 0.6


def test_property_papers_not_confused_with_valuation():
    # An ownership certificate should read as property papers, not a valuation report.
    result = classify_document(PROPERTY_TEXT)
    assert result["detected_document_type"] == PROPERTY_PAPERS
