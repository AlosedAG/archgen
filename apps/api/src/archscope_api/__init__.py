"""ArchitectureScope HTTP API.

Layering (enforced by import-linter, see the root pyproject):

- ``routers``  — HTTP only: parse/validate requests, map schemas <-> domain,
  pick status codes and media types. No business logic.
- ``services`` — use cases: orchestrate domain functions and adapters.
  Speak domain types only; never import HTTP schemas.
- ``schemas``  — the public API contract (Pydantic v2), with explicit
  ``to_domain`` / ``from_domain`` mappers. Domain types never leak into
  responses directly, so the contract can stay stable while the domain evolves.
"""
