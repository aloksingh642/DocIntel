"""OpenAI-backed extraction provider.

Sends the strict prompts, then validates the model output through the same
Pydantic schemas every provider uses. Malformed JSON triggers one safe-parse
retry; persistent failure raises AIOutputError so the pipeline marks the
stage failed and logs it (never silently storing unvalidated output).
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from app.ai.base import LLMProvider
from app.ai.prompts import CLASSIFICATION_PROMPT, RESUME_EXTRACTION_PROMPT
from app.config import settings
from app.schemas.extraction import DocumentClassification, ExtractionResult


class AIOutputError(Exception):
    pass


def _safe_parse_json(raw: str) -> dict:
    """Best-effort JSON extraction (handles code fences and stray prose)."""
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start : end + 1])
        raise


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.AI_API_KEY:
            raise AIOutputError("AI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise AIOutputError("openai package not installed.") from exc
        self._client = OpenAI(api_key=settings.AI_API_KEY)

    def _chat_json(self, prompt: str) -> dict:
        resp = self._client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = resp.choices[0].message.content or "{}"
        return _safe_parse_json(raw)

    def extract_resume(self, text: str) -> ExtractionResult:
        try:
            data = self._chat_json(RESUME_EXTRACTION_PROMPT.format(text=text[:12000]))
            return ExtractionResult.model_validate(data)
        except (ValidationError, json.JSONDecodeError, KeyError) as exc:
            # single retry for malformed output
            try:
                data = self._chat_json(RESUME_EXTRACTION_PROMPT.format(text=text[:12000]))
                return ExtractionResult.model_validate(data)
            except Exception as retry_exc:
                raise AIOutputError(f"Extraction output failed validation: {retry_exc}") from exc

    def classify_document(self, text: str) -> DocumentClassification:
        try:
            data = self._chat_json(CLASSIFICATION_PROMPT.format(text=text[:6000]))
            return DocumentClassification.model_validate(data)
        except Exception as exc:
            raise AIOutputError(f"Classification output failed validation: {exc}") from exc
