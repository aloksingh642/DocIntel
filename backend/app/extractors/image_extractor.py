"""Image extraction: preprocess -> OCR."""
from __future__ import annotations

from pathlib import Path

from app.extractors.base import ExtractionOutput, TextExtractor
from app.extractors.ocr import OCRUnavailable, ocr_image


class ImageExtractor(TextExtractor):
    def extract(self, path: Path) -> ExtractionOutput:
        # Raises OCRUnavailable when Tesseract is missing; the pipeline stage
        # converts that into a clean, logged "failed" status for the document.
        text = ocr_image(path).strip()
        return ExtractionOutput(text=text or "", pages=[text], used_ocr=True,
                                metadata={"format": "image"})
