"""Plain-text extraction with encoding fallback."""
from __future__ import annotations

from pathlib import Path

from app.extractors.base import ExtractionError, ExtractionOutput, TextExtractor

_ENCODINGS = ("utf-8", "utf-16", "latin-1")


class TxtExtractor(TextExtractor):
    def extract(self, path: Path) -> ExtractionOutput:
        for enc in _ENCODINGS:
            try:
                text = path.read_text(encoding=enc).strip()
                if text:
                    return ExtractionOutput(text=text, pages=[text], metadata={"encoding": enc})
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ExtractionError("TXT file is empty or could not be decoded.")
