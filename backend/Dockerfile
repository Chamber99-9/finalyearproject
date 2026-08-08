# Sajilo Loan API — production container.
# Python 3.11 is required (the code uses datetime.UTC and enum.StrEnum).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # The OCR module (pytesseract) needs the real binary path on Linux.
    TESSERACT_CMD=/usr/bin/tesseract \
    # Uploaded documents live here; mount a persistent disk at this path in
    # production to keep them across redeploys (see DEPLOYMENT.md).
    UPLOAD_DIR=/app/uploads

# System dependency: the Tesseract OCR engine + English and Nepali (Devanagari)
# language data. tesseract-ocr-nep lets OCR read Nepali names/text on documents.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-nep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so Docker can cache this layer.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application source.
COPY . .

# Ensure the upload directory exists.
RUN mkdir -p "$UPLOAD_DIR"

# Documented default; hosting platforms (Render/Railway) inject their own $PORT.
EXPOSE 8000

# Bind to 0.0.0.0 and honor the platform-provided $PORT (fallback 8000 locally).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
