"""Public API contract (Pydantic v2). The OpenAPI document — and the
generated TypeScript client — are derived from these models."""

from .common import Health, Problem

__all__ = ["Health", "Problem"]
