from pathlib import Path
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from PIL import Image, UnidentifiedImageError
import pytesseract

from app.config import get_settings
from app.models.ocr import create_ocr_result_document, ocr_result_id_to_str
from app.services.document_classifier import classify_document

OCR_RESULTS_COLLECTION = "ocr_results"
DEFAULT_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)
SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class UnsupportedOCRFileError(Exception):
    pass


class OCRFileNotFoundError(Exception):
    pass


class OCRUnreadableFileError(Exception):
    pass


class EmptyOCRTextError(Exception):
    pass


class OCRProcessingError(Exception):
    pass


class OCRNotConfiguredError(Exception):
    pass


class OCRResultStorageError(Exception):
    pass


class OCRResultNotFoundError(Exception):
    pass


def serialize_ocr_result(document: dict[str, Any]) -> dict[str, Any]:
    return ocr_result_id_to_str(document)


def calculate_confidence(confidence_values: list[str]) -> float | None:
    numeric_values: list[float] = []
    for value in confidence_values:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            continue

        if confidence >= 0:
            numeric_values.append(confidence)

    if not numeric_values:
        return None
    return round(sum(numeric_values) / len(numeric_values), 2)


def configure_tesseract_command() -> None:
    tesseract_cmd = get_settings().tesseract_cmd.strip()
    if tesseract_cmd:
        tesseract_path = Path(tesseract_cmd)
    else:
        tesseract_path = next(
            (path for path in DEFAULT_TESSERACT_PATHS if path.is_file()),
            None,
        )

    if tesseract_path is None or not tesseract_path.is_file():
        raise OCRNotConfiguredError

    pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)


async def extract_and_save_ocr_result(
    *,
    database: AsyncIOMotorDatabase,
    document: dict[str, Any],
) -> dict[str, Any]:
    content_type = document.get("content_type")
    if content_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
        raise UnsupportedOCRFileError

    file_path = Path(str(document.get("file_path", "")))
    if not file_path.is_file():
        raise OCRFileNotFoundError

    try:
        with Image.open(file_path) as image:
            image.load()
            normalized_image = image.convert("RGB")
    except UnidentifiedImageError as error:
        raise OCRUnreadableFileError from error
    except OSError as error:
        raise OCRUnreadableFileError from error

    try:
        configure_tesseract_command()
        ocr_data = pytesseract.image_to_data(
            normalized_image,
            output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractNotFoundError as error:
        raise OCRNotConfiguredError from error
    except pytesseract.TesseractError as error:
        raise OCRProcessingError from error

    text_values = [value.strip() for value in ocr_data.get("text", []) if value.strip()]
    extracted_text = " ".join(text_values).strip()
    if not extracted_text:
        raise EmptyOCRTextError

    confidence_score = calculate_confidence(ocr_data.get("conf", []))
    # Detect what kind of document this is from its text, and check it against
    # the type the customer selected for this upload slot.
    classification = classify_document(
        extracted_text,
        expected_document_type=document.get("document_type"),
    )
    result_document = create_ocr_result_document(
        document_id=str(document.get("id") or document.get("_id")),
        application_id=str(document["application_id"]),
        extracted_text=extracted_text,
        confidence_score=confidence_score,
        classification=classification,
    )

    try:
        result = await database[OCR_RESULTS_COLLECTION].insert_one(result_document)
    except Exception as error:
        raise OCRResultStorageError from error

    result_document["_id"] = result.inserted_id
    return result_document


async def get_ocr_result_by_id(
    database: AsyncIOMotorDatabase,
    ocr_result_id: str,
) -> dict[str, Any] | None:
    if not ObjectId.is_valid(ocr_result_id):
        return None

    return await database[OCR_RESULTS_COLLECTION].find_one(
        {"_id": ObjectId(ocr_result_id)}
    )


async def get_latest_ocr_result_for_document(
    database: AsyncIOMotorDatabase,
    document_id: str,
) -> dict[str, Any] | None:
    return await database[OCR_RESULTS_COLLECTION].find_one(
        {"document_id": document_id},
        sort=[("created_at", -1)],
    )


async def verify_ocr_result(
    *,
    database: AsyncIOMotorDatabase,
    ocr_result_id: str,
    corrected_data: dict[str, Any],
) -> dict[str, Any]:
    if not ObjectId.is_valid(ocr_result_id):
        raise OCRResultNotFoundError

    result = await database[OCR_RESULTS_COLLECTION].find_one_and_update(
        {"_id": ObjectId(ocr_result_id)},
        {
            "$set": {
                "verified_by_user": True,
                "corrected_data": corrected_data,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if result is None:
        raise OCRResultNotFoundError
    return result
