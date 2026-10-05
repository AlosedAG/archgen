"""Base classes and domain mappers shared by every schema module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter


class ApiModel(BaseModel):
    """Every API model: unknown inbound fields are rejected (never silently
    dropped), and models can be built from domain objects' attributes."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


_ADAPTERS: dict[type[Any], TypeAdapter[Any]] = {}


def _adapter(cls: type[Any]) -> TypeAdapter[Any]:
    """Validators are built once per domain type (building one is costly)."""
    if cls not in _ADAPTERS:
        _ADAPTERS[cls] = TypeAdapter(cls)
    return _ADAPTERS[cls]


def to_domain[D](model: BaseModel, cls: type[D], **overrides: Any) -> D:
    """Build a (nested) domain dataclass from an API model. Pydantic
    validates straight into stdlib dataclasses, so nested objects come out
    as the real domain types rather than dicts."""
    result: D = _adapter(cls).validate_python({**model.model_dump(), **overrides})
    return result
