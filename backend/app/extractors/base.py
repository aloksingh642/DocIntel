"""Base text-extractor interface — implementations are individually testable."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractionOutput:
    text: str
    pages: list[str] = field(default_factory=list)  # page boundaries preserved
    used_ocr: bool = False
    metadata: dict = field(default_factory=dict)


class TextExtractor(ABC):
    """Contract implemented by every file-type extractor."""

    @abstractmethod
    def extract(self, path: Path) -> ExtractionOutput:
        """Extract text from a file, raising ExtractionError on failure."""


class ExtractionError(Exception):
    pass
