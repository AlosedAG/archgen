"""Ports — the interfaces the domain needs from the outside world.

The domain never talks to HubSpot directly. Portal pulls (``docgen``) and
record-level audit checks (``audit``, ``property_audit``) depend only on
:class:`PortalReader`; ``archscope_integrations.hubspot.HubSpotClient``
is the production adapter, and tests pass in-memory fakes.

The protocol is deliberately read-only: it has no create/update/delete
methods, so no domain code *can* mutate a connected portal.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# (API object type, display label) for the standard objects this tool understands.
STANDARD_OBJECT_TYPES: list[tuple[str, str]] = [
    ("contacts", "Contact"),
    ("companies", "Company"),
    ("deals", "Deal"),
    ("tickets", "Ticket"),
]


class PortalScopeError(RuntimeError):
    """The portal rejected a read (HTTP 401/403): missing scope or bad token."""


class PortalAPIError(RuntimeError):
    """Any other failure reading the portal (rate-limit exhaustion, 404, 5xx)."""


@runtime_checkable
class PortalReader(Protocol):
    """Read-only access to one CRM portal. Every method may raise
    :class:`PortalScopeError` or :class:`PortalAPIError`; domain code
    catches both and records a warning rather than failing the whole run."""

    def get_custom_object_schemas(self) -> list[dict[str, Any]]: ...

    def get_properties(self, object_type: str) -> list[dict[str, Any]]: ...

    def get_pipelines(self, object_type: str) -> list[dict[str, Any]]: ...

    def get_owners(self) -> list[dict[str, Any]]: ...

    def get_teams(self) -> list[dict[str, Any]]: ...

    def get_workflows(self) -> list[dict[str, Any]]: ...

    def get_workflow_detail(self, workflow_id: Any) -> dict[str, Any]: ...

    def get_records_sample(
        self, object_type: str, limit: int = 100, properties: list[str] | None = None
    ) -> list[dict[str, Any]]: ...

    def get_associations_sample(
        self, from_object_type: str, to_object_type: str, object_ids: list[str]
    ) -> dict[str, list[str]]: ...
