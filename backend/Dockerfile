FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Tesseract enables the OCR pipeline for image and scanned-PDF documents.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# The frontend dist (if built) is served at /; API at /api/v1.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
