"""Provider factory — selects the AI backend from configuration."""
from __future__ import annotations

from app.ai.base import LLMProvider
from app.config import settings

_PROVIDER_CACHE: dict[str, LLMProvider] = {}


def get_llm_provider(force: str | None = None) -> LLMProvider:
    name = (force or settings.AI_PROVIDER).lower()
    if name not in _PROVIDER_CACHE:
        if name == "openai":
            from app.ai.openai_provider import OpenAIProvider

            _PROVIDER_CACHE[name] = OpenAIProvider()
        else:  # default: deterministic offline provider
            from app.ai.mock_provider import MockLLMProvider

            _PROVIDER_CACHE[name] = MockLLMProvider()
    return _PROVIDER_CACHE[name]
