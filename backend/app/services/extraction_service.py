"""Information-extraction service: provider call + schema validation + retry."""
from __future__ import annotations

from pydantic import ValidationError

from app.ai.factory import get_llm_provider
from app.schemas.extraction import ExtractionResult


class ExtractionValidationError(Exception):
    pass


class ExtractionService:
    def extract_resume(self, text: str) -> ExtractionResult:
        provider = get_llm_provider()
        try:
            result = provider.extract_resume(text)
            # Always validate — providers must never bypass the schema.
            return ExtractionResult.model_validate(result.model_dump())
        except ValidationError as exc:
            try:  # single retry before the pipeline marks the stage failed
                result = provider.extract_resume(text)
                return ExtractionResult.model_validate(result.model_dump())
            except Exception as final_exc:
                raise ExtractionValidationError(
                    f"AI extraction output failed schema validation: {final_exc}"
                ) from exc
