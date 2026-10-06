"""Read-only HubSpot API client.

Wraps the official ``hubspot-api-client`` SDK for the endpoints it covers
reliably (object schemas, properties, pipelines, owners, record objects,
association batch-reads), and falls back to ``requests`` for endpoints the
SDK covers inconsistently across versions: legacy workflow automation and
the Settings teams API.

This tool is read-only end to end: every HubSpot call here is a GET, or a
POST against one of HubSpot's "batch read" query endpoints (which do not
mutate data despite the HTTP verb — that's simply how HubSpot's batch APIs
are designed). HubSpotClient exposes no create/update/delete methods; it
implements the domain's read-only :class:`archscope_domain.ports.PortalReader`.

Every call is wrapped so a rate limit (429) is retried with backoff, a
missing-scope or invalid-token response (401/403) is raised as
``HubSpotScopeError``, and any other API failure is raised as
``HubSpotAPIError`` — the domain's port errors, so domain code
(docgen/audit) catches them without importing this adapter.

The token is always passed in explicitly: resolving it (environment,
encrypted credential store, UI session) is the caller's job.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

import requests
from hubspot import HubSpot

from archscope_domain.ports import STANDARD_OBJECT_TYPES  # noqa: F401 — re-exported
from archscope_domain.ports import PortalAPIError as HubSpotAPIError
from archscope_domain.ports import PortalScopeError as HubSpotScopeError

BASE_URL = "https://api.hubapi.com"

JSON = dict[str, Any]
_T = TypeVar("_T")

MAX_RETRIES = 5
DEFAULT_BACKOFF_SECONDS = 2.0


class HubSpotClient:
    """Read-only client for pulling data from a HubSpot portal."""

    def __init__(self, token: str):
        if not token:
            raise ValueError("A HubSpot private app access token is required.")
        self.token = token
        self._sdk = HubSpot(access_token=self.token)
        self._session = requests.Session()

    # ---- retry/error handling for SDK calls ------------------------------

    def _call_with_retry(self, fn: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        attempt = 0
        while True:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # hubspot-api-client raises a per-module ApiException
                status = getattr(exc, "status", None)
                if status == 429:
                    attempt += 1
                    if attempt > MAX_RETRIES:
                        raise HubSpotAPIError(f"Rate limited repeatedly; gave up after {MAX_RETRIES} retries.") from exc
                    headers = getattr(exc, "headers", None) or {}
                    retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
                    delay = float(retry_after) if retry_after else DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    time.sleep(delay)
                    continue
                if status in (401, 403):
                    raise HubSpotScopeError(
                        f"HubSpot rejected this request (HTTP {status}). The token is likely "
                        "missing a required scope, or is invalid/expired — see the README for "
                        "the exact scopes needed."
                    ) from exc
                if status == 404:
                    raise HubSpotAPIError("Not found (HTTP 404) — this portal may not have this object/feature.") from exc
                raise HubSpotAPIError(f"HubSpot API error: {exc}") from exc

    # ---- requests-based fallback (workflows, teams) ----------------------
    # GET only, by construction: there is no generic request method, so this
    # client cannot issue a write through the requests fallback.

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> JSON:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        attempt = 0
        while True:
            response = self._session.get(url, headers=self._headers(), timeout=30, params=params)
            if response.status_code == 429:
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise HubSpotAPIError(f"Rate limited repeatedly calling {url}; gave up after {MAX_RETRIES} retries.")
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1))
                time.sleep(delay)
                continue
            if response.status_code in (401, 403):
                raise HubSpotScopeError(
                    f"HubSpot rejected this request (HTTP {response.status_code}) calling {url}. "
                    "The token is likely missing a required scope, or is invalid/expired — see "
                    "the README for the exact scopes needed."
                )
            if response.status_code == 404:
                raise HubSpotAPIError(f"Not found calling {url} (HTTP 404). This portal may not have this feature.")
            if not response.ok:
                raise HubSpotAPIError(f"HubSpot API error calling {url}: HTTP {response.status_code} — {response.text[:300]}")
            if not response.content:
                return {}
            data: JSON = response.json()
            return data

    # ---- pulls: schemas, properties, pipelines, owners (via SDK) ---------

    def get_custom_object_schemas(self) -> list[JSON]:
        """All custom object schemas defined in the portal."""
        result = self._call_with_retry(self._sdk.crm.schemas.core_api.get_all)
        return [r.to_dict() for r in (result.results or [])]

    def get_properties(self, object_type: str) -> list[JSON]:
        """All properties (standard or custom) for the given object type."""
        result = self._call_with_retry(self._sdk.crm.properties.core_api.get_all, object_type=object_type)
        return [r.to_dict() for r in (result.results or [])]

    def get_pipelines(self, object_type: str) -> list[JSON]:
        """All pipelines (with stages) for the given object type."""
        try:
            result = self._call_with_retry(self._sdk.crm.pipelines.pipelines_api.get_all, object_type=object_type)
        except HubSpotAPIError:
            # Not every object type has pipelines (HubSpot 404s cleanly) — treat as "none".
            return []
        return [r.to_dict() for r in (result.results or [])]

    def get_owners(self) -> list[JSON]:
        """All owners in the portal, paginated."""
        owners: list[JSON] = []
        after: str | None = None
        while True:
            kwargs: dict[str, Any] = {"limit": 100}
            if after:
                kwargs["after"] = after
            page = self._call_with_retry(self._sdk.crm.owners.owners_api.get_page, **kwargs)
            owners.extend(r.to_dict() for r in (page.results or []))
            paging = getattr(page, "paging", None)
            next_page = getattr(paging, "next", None) if paging else None
            after = getattr(next_page, "after", None) if next_page else None
            if not after:
                break
        return owners

    def get_records_sample(self, object_type: str, limit: int = 100, properties: list[str] | None = None) -> list[JSON]:
        """Up to `limit` records of the given object type (sampled, not exhaustive)."""
        records: list[JSON] = []
        after: str | None = None
        page_size = min(limit, 100)
        while len(records) < limit:
            kwargs: dict[str, Any] = {"limit": page_size, "properties": properties or []}
            if after:
                kwargs["after"] = after
            page = self._call_with_retry(self._sdk.crm.objects.basic_api.get_page, object_type, **kwargs)
            records.extend(r.to_dict() for r in (page.results or []))
            paging = getattr(page, "paging", None)
            next_page = getattr(paging, "next", None) if paging else None
            after = getattr(next_page, "after", None) if next_page else None
            if not after:
                break
        return records[:limit]

    def get_associations_sample(self, from_object_type: str, to_object_type: str, object_ids: list[str]) -> dict[str, list[str]]:
        """Batch-read association targets for a sample of record IDs.

        Uses HubSpot's CRM v3 batch associations "read" endpoint — a
        read-only query even though it's a POST under the hood (HubSpot's
        batch endpoints are POST-based by API design, not a mutation).
        Returns {record_id: [associated_record_id, ...]}.
        """
        if not object_ids:
            return {}
        from hubspot.crm.associations import BatchInputPublicObjectId, PublicObjectId

        batch_input = BatchInputPublicObjectId(inputs=[PublicObjectId(id=oid) for oid in object_ids])
        try:
            result = self._call_with_retry(
                self._sdk.crm.associations.batch_api.read,
                from_object_type,
                to_object_type,
                batch_input,
            )
        except HubSpotAPIError:
            return {}
        mapping: dict[str, list[str]] = {}
        for item in result.results or []:
            item_dict = item.to_dict()
            from_id = (item_dict.get("_from") or {}).get("id")
            to_ids = [t.get("id") for t in (item_dict.get("to") or [])]
            if from_id:
                mapping[from_id] = to_ids
        return mapping

    # ---- pulls: workflows, teams (requests fallback) ----------------------

    def get_workflows(self) -> list[JSON]:
        """Legacy v3 workflow summaries (scope: automation). See get_workflow_detail
        for the full action list needed to check re-enrollment/overwrite risk."""
        data = self._get("/automation/v3/workflows")
        workflows: list[JSON] = data.get("workflows", [])
        return workflows

    def get_workflow_detail(self, workflow_id: Any) -> JSON:
        return self._get(f"/automation/v3/workflows/{workflow_id}")

    def get_teams(self) -> list[JSON]:
        try:
            data = self._get("/settings/v3/users/teams")
        except HubSpotAPIError:
            return []
        teams: list[JSON] = data.get("results", [])
        return teams
