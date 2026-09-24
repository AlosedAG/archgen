"""Read-only HubSpot API client.

Wraps the official ``hubspot-api-client`` SDK for the endpoints it covers
reliably (object schemas, properties, pipelines, owners, record objects,
association batch-reads), and falls back to ``requests`` for endpoints the
SDK covers inconsistently across versions: legacy workflow automation and
the Settings teams API.

This tool is read-only end to end: every HubSpot call here is a GET, or a
POST against one of HubSpot's "batch read" query endpoints (which do not
mutate data despite the HTTP verb — that's simply how HubSpot's batch APIs
are designed). HubSpotClient exposes no create/update/delete methods.

Every call is wrapped so a rate limit (429) is retried with backoff, a
missing-scope or invalid-token response (401/403) is raised as
``HubSpotScopeError``, and any other API failure is raised as
``HubSpotAPIError`` — callers (docgen/audit/pages) catch these and show a
clear message instead of crashing.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests
from hubspot import HubSpot

try:
    import streamlit as st
except ImportError:  # pragma: no cover - streamlit is a hard dependency at runtime
    st = None

BASE_URL = "https://api.hubapi.com"

# (API object type, display label) for the standard objects this tool understands.
STANDARD_OBJECT_TYPES: list[tuple[str, str]] = [
    ("contacts", "Contact"),
    ("companies", "Company"),
    ("deals", "Deal"),
    ("tickets", "Ticket"),
]

MAX_RETRIES = 5
DEFAULT_BACKOFF_SECONDS = 2.0


def get_token() -> Optional[str]:
    """Resolve the HubSpot private-app access token.

    Checks the ``HUBSPOT_TOKEN`` environment variable first, then falls back
    to a token the user entered into a Streamlit text input this session.
    The token is only ever held in ``st.session_state`` — never written to
    disk, never logged.
    """
    env_token = os.environ.get("HUBSPOT_TOKEN")
    if env_token:
        return env_token
    if st is not None:
        try:
            session_token = st.session_state.get("hubspot_token")
        except Exception:
            session_token = None
        if session_token:
            return session_token
    return None


class HubSpotScopeError(RuntimeError):
    """Raised when the token is missing a required scope, or is invalid/expired."""


class HubSpotAPIError(RuntimeError):
    """Raised for any other non-recoverable HubSpot API failure."""


class HubSpotClient:
    """Read-only client for pulling data from a HubSpot portal."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or get_token()
        if not self.token:
            raise ValueError(
                "No HubSpot token found. Set the HUBSPOT_TOKEN environment "
                "variable, or enter a private app access token in the UI."
            )
        self._sdk = HubSpot(access_token=self.token)
        self._session = requests.Session()

    # ---- retry/error handling for SDK calls ------------------------------

    def _call_with_retry(self, fn, *args, **kwargs):
        attempt = 0
        while True:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # hubspot-api-client raises a per-module ApiException
                status = getattr(exc, "status", None)
                if status == 429:
                    attempt += 1
                    if attempt > MAX_RETRIES:
                        raise HubSpotAPIError(
                            f"Rate limited repeatedly; gave up after {MAX_RETRIES} retries."
                        ) from exc
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
                    raise HubSpotAPIError(
                        "Not found (HTTP 404) — this portal may not have this object/feature."
                    ) from exc
                raise HubSpotAPIError(f"HubSpot API error: {exc}") from exc

    # ---- requests-based fallback (workflows, teams) ----------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, **kwargs) -> dict:
        attempt = 0
        while True:
            response = self._session.request(method, url, headers=self._headers(), timeout=30, **kwargs)
            if response.status_code == 429:
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise HubSpotAPIError(
                        f"Rate limited repeatedly calling {url}; gave up after {MAX_RETRIES} retries."
                    )
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
            return response.json()

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        return self._request("GET", url, params=params)

    # ---- pulls: schemas, properties, pipelines, owners (via SDK) ---------

    def get_custom_object_schemas(self) -> list[dict]:
        """All custom object schemas defined in the portal."""
        result = self._call_with_retry(self._sdk.crm.schemas.core_api.get_all)
        return [r.to_dict() for r in (result.results or [])]

    def get_properties(self, object_type: str) -> list[dict]:
        """All properties (standard or custom) for the given object type."""
        result = self._call_with_retry(self._sdk.crm.properties.core_api.get_all, object_type=object_type)
        return [r.to_dict() for r in (result.results or [])]

    def get_pipelines(self, object_type: str) -> list[dict]:
        """All pipelines (with stages) for the given object type."""
        try:
            result = self._call_with_retry(self._sdk.crm.pipelines.pipelines_api.get_all, object_type=object_type)
        except HubSpotAPIError:
            # Not every object type has pipelines (HubSpot 404s cleanly) — treat as "none".
            return []
        return [r.to_dict() for r in (result.results or [])]

    def get_owners(self) -> list[dict]:
        """All owners in the portal, paginated."""
        owners: list[dict] = []
        after: Optional[str] = None
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

    def get_records_sample(
        self, object_type: str, limit: int = 100, properties: Optional[list[str]] = None
    ) -> list[dict]:
        """Up to `limit` records of the given object type (sampled, not exhaustive)."""
        records: list[dict] = []
        after: Optional[str] = None
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

    def get_associations_sample(
        self, from_object_type: str, to_object_type: str, object_ids: list[str]
    ) -> dict[str, list[str]]:
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

    def get_workflows(self) -> list[dict]:
        """Legacy v3 workflow summaries (scope: automation). See get_workflow_detail
        for the full action list needed to check re-enrollment/overwrite risk."""
        data = self._get("/automation/v3/workflows")
        return data.get("workflows", [])

    def get_workflow_detail(self, workflow_id) -> dict:
        return self._get(f"/automation/v3/workflows/{workflow_id}")

    def get_teams(self) -> list[dict]:
        try:
            data = self._get("/settings/v3/users/teams")
        except HubSpotAPIError:
            return []
        return data.get("results", [])
