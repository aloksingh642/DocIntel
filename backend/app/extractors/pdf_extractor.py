"""PDF text extraction with automatic OCR fallback for scanned documents."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.extractors.base import ExtractionError, ExtractionOutput, TextExtractor
from app.extractors.ocr import OCRUnavailable, ocr_image

MIN_CHARS_PER_TABLE_PAGE = 40  # below this, a page is treated as a scan/image


class PdfExtractor(TextExtractor):
    def extract(self, path: Path) -> ExtractionOutput:
        try:
            reader = PdfReader(str(path))
        except Exception as exc:  # corrupted / encrypted PDF
            raise ExtractionError(f"Unable to read PDF: {exc.__class__.__name__}") from exc

        pages: list[str] = []
        used_ocr = False
        was_scanned = False
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append(text)
            if len(text.strip()) < MIN_CHARS_PER_TABLE_PAGE:
                was_scanned = True

        # Image-based PDF pages go through OCR (rendered by pypdf's image extraction
        # where possible); if OCR is unavailable, keep whatever text we have.
        if was_scanned:
            for page in reader.pages:
                try:
                    for image_file in page.images:
                        tmp = path.parent / f".__ocr_tmp_{image_file.name}"
                        try:
                            tmp.write_bytes(image_file.data)
                            pages.append(ocr_image(tmp))
                            used_ocr = True
                        finally:
                            tmp.unlink(missing_ok=True)
                except OCRUnavailable:
                    break
                except Exception:
                    continue  # keep direct text we already have

        full_text = "\n\n".join(pages).strip()
        if not full_text and was_scanned:
            raise ExtractionError(
                "PDF appears to be scanned/image-based and OCR produced no text "
                "(OCR engine may be unavailable on this host)."
            )
        if not full_text:
            raise ExtractionError("PDF contains no extractable text.")
        return ExtractionOutput(
            text=full_text,
            pages=pages,
            used_ocr=used_ocr,
            metadata={"page_count": len(reader.pages), "scanned": was_scanned},
        )
