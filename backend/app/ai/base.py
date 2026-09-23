"""AI provider abstraction — the application never hard-codes one provider.

Switch providers via the AI_PROVIDER environment variable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.extraction import DocumentClassification, ExtractionResult


class LLMProvider(ABC):
    """Contract every extraction/classification provider must implement."""

    name: str = "abstract"

    @abstractmethod
    def extract_resume(self, text: str) -> ExtractionResult:
        """Extract structured resume data. Must never invent information:
        unavailable scalars are None, unavailable lists are []."""

    @abstractmethod
    def classify_document(self, text: str) -> DocumentClassification:
        """Classify the document into a known type with a confidence score."""
