"""OCR pipeline: preprocessing -> OCR.

Preprocessing steps: resize, grayscale, noise reduction, thresholding.
Uses Tesseract via pytesseract when the binary is available; degrades
gracefully (raises OCRUnavailable) otherwise so the pipeline can fail
the stage cleanly without crashing the worker.
"""
from __future__ import annotations

import shutil
from pathlib import Path

try:
    import pytesseract  # type: ignore
    from PIL import Image, ImageFilter, ImageOps

    _PYTESSERACT_IMPORTABLE = True
except Exception:  # pragma: no cover - optional dependency
    _PYTESSERACT_IMPORTABLE = False


class OCRUnavailable(Exception):
    pass


def tesseract_available() -> bool:
    return _PYTESSERACT_IMPORTABLE and shutil.which("tesseract") is not None


def preprocess_image(image: "Image.Image") -> "Image.Image":
    """Grayscale, upscale small images, denoise, autocontrast/threshold."""
    image = ImageOps.grayscale(image)
    if max(image.size) < 1500:  # upscale low-res scans for better OCR
        ratio = 1500 / max(image.size)
        image = image.resize(
            (int(image.width * ratio), int(image.height * ratio)), Image.LANCZOS
        )
    image = image.filter(ImageFilter.MedianFilter(size=3))  # noise reduction
    image = ImageOps.autocontrast(image)
    return image


def ocr_image(path: Path) -> str:
    """Run OCR on a single image file; returns text or raises OCRUnavailable."""
    if not tesseract_available():
        raise OCRUnavailable(
            "OCR engine (Tesseract) is not installed on this host."
        )
    with Image.open(path) as im:
        return pytesseract.image_to_string(preprocess_image(im))
