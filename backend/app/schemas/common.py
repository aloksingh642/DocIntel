"""Shared API envelope and pagination schemas."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str


class APIResponse(BaseModel):
    """Consistent success response: {success, data, message}."""

    success: bool = True
    data: Any = None
    message: str | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
