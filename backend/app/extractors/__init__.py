"""Extractor registry — maps file extensions to extractor implementations.

Adding a new document type = adding one module and one registry entry.
"""
from __future__ import annotations

from app.extractors.base import ExtractionError, ExtractionOutput, TextExtractor
from app.extractors.docx_extractor import DocxExtractor
from app.extractors.image_extractor import ImageExtractor
from app.extractors.pdf_extractor import PdfExtractor
from app.extractors.txt_extractor import TxtExtractor

_REGISTRY: dict[str, TextExtractor] = {
    ".pdf": PdfExtractor(),
    ".docx": DocxExtractor(),
    ".txt": TxtExtractor(),
    ".jpg": ImageExtractor(),
    ".jpeg": ImageExtractor(),
    ".png": ImageExtractor(),
}


def get_extractor(ext: str) -> TextExtractor:
    extractor = _REGISTRY.get(ext.lower())
    if extractor is None:
        raise ExtractionError(f"No extractor registered for '{ext}'.")
    return extractor


__all__ = ["ExtractionError", "ExtractionOutput", "TextExtractor", "get_extractor"]
