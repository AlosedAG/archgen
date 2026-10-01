"""API-key inputs shared by the Setup page and every page that needs a key.

Two credentials exist in this app:

- **HubSpot private app token** — read-only access to a live portal
  (Portal Auditor, Property Audit, Documentation Generator).
- **Anthropic API key** — the Discovery Call Assistant's AI drafting.

Both resolve the same way: an environment variable first (``HUBSPOT_TOKEN``
/ ``ANTHROPIC_API_KEY``, also read from a local ``.env`` file), then a value
pasted into the UI this session. A pasted value is held only in
``st.session_state`` — never written to disk, never logged.

Why the indirection through a separate widget key: Streamlit deletes a
widget's session_state entry whenever a run doesn't render that widget —
i.e. as soon as the user switches to another page. Pasting a key straight
into ``key="hubspot_token"`` would therefore silently "forget" it the moment
the user left the Setup page. Instead the input writes to a private widget
key, and an ``on_change`` callback copies the value into the plain
(non-widget) key the rest of the app reads, which survives page switches.
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st

from core.hubspot_client import get_token

try:  # .env support is a convenience, not a requirement
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

HUBSPOT_SESSION_KEY = "hubspot_token"
ANTHROPIC_SESSION_KEY = "anthropic_api_key"
ANTHROPIC_ENV_VAR = "ANTHROPIC_API_KEY"
SETUP_URL = "/Setup"


def get_anthropic_key() -> Optional[str]:
    """Anthropic API key from ``ANTHROPIC_API_KEY``, else this session."""
    env_key = os.environ.get(ANTHROPIC_ENV_VAR)
    if env_key:
        return env_key
    return st.session_state.get(ANTHROPIC_SESSION_KEY) or None


def _copy_widget_value(widget_key: str, session_key: str) -> None:
    value = (st.session_state.get(widget_key) or "").strip()
    if value:
        st.session_state[session_key] = value
    st.session_state[widget_key] = ""


def _forget(session_key: str) -> None:
    st.session_state.pop(session_key, None)


def _key_input(*, label: str, session_key: str, env_var: str, current: Optional[str], help_text: str) -> None:
    """Status line + password input (+ a "forget" button for a pasted key)."""
    from_env = bool(os.environ.get(env_var))
    if current:
        source = f"from the `{env_var}` environment variable" if from_env else "pasted this session"
        st.success(f"Connected — key {source} (ends in …{current[-4:]}).")
        if not from_env:
            st.button("Forget this key", key=f"forget_{session_key}", on_click=_forget, args=(session_key,), type="secondary")
        return
    widget_key = f"_{session_key}_widget"
    st.text_input(
        label,
        type="password",
        key=widget_key,
        on_change=_copy_widget_value,
        args=(widget_key, session_key),
        help=help_text,
        placeholder="Paste and press Enter",
    )


def hubspot_token_input() -> None:
    _key_input(
        label="HubSpot private app access token",
        session_key=HUBSPOT_SESSION_KEY,
        env_var="HUBSPOT_TOKEN",
        current=get_token(),
        help_text="Stored only in this session's memory — never written to disk or logged. "
        "You can also set the HUBSPOT_TOKEN environment variable (or put it in .env).",
    )


def anthropic_key_input() -> None:
    _key_input(
        label="Anthropic API key",
        session_key=ANTHROPIC_SESSION_KEY,
        env_var=ANTHROPIC_ENV_VAR,
        current=get_anthropic_key(),
        help_text="Used only to draft Discovery Call Assistant documents. Stored only in this "
        "session's memory — never written to disk or logged. You can also set the "
        "ANTHROPIC_API_KEY environment variable (or put it in .env).",
    )


def require_hubspot_token() -> bool:
    """For pages that read a live portal: show the token input inline when
    no token is set yet (so nobody has to bounce back to Setup), plus a
    pointer to the Setup page's full instructions. Returns whether a token
    is available."""
    if get_token():
        st.success("HubSpot token detected.")
        return True
    st.warning("This page reads a live HubSpot portal and needs a private app access token.")
    hubspot_token_input()
    # A plain link rather than st.page_link: page_link raises when a page
    # script runs outside the router (e.g. in the standalone AppTest smoke tests).
    st.markdown(f"How do I get a token? See [Setup & API keys]({SETUP_URL}).")
    return False
