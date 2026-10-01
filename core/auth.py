"""Login gate — every page sits behind it (called from Home.py before
``st.navigation``).

Two ways in, both configured in ``.streamlit/secrets.toml`` (locally) or
the app's Secrets box on Streamlit Community Cloud:

- **Google sign-in** via Streamlit's built-in OIDC support
  (``st.login`` / ``st.user``), enabled by an ``[auth]`` section. Anyone
  with a Google account can complete Google's sign-in, so access is then
  limited by ``[access] allowed_emails`` / ``allowed_domains``.
- **Username + password**, enabled by a ``[passwords]`` section mapping
  usernames to passwords. Values may be plain text or, preferably, a hash
  made with ``python -m core.auth``.

With neither configured the app refuses to open (fail closed), so a
deploy with missing secrets never ends up public. For local development,
set ``AUTH_DISABLED=1`` (environment or ``.env``) to skip the gate.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets as _secrets
import time
from typing import Any, Optional

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is in requirements.txt
    pass

PASSWORD_SESSION_KEY = "_auth_password_user"
_HASH_PREFIX = "pbkdf2_sha256"
_HASH_ITERATIONS = 600_000


def hash_password(password: str, *, iterations: int = _HASH_ITERATIONS) -> str:
    """``pbkdf2_sha256$<iterations>$<salt>$<hex digest>`` for ``[passwords]``."""
    salt = _secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"{_HASH_PREFIX}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith(_HASH_PREFIX + "$"):
        try:
            _, iterations, salt, digest = stored.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        except ValueError:
            return False
        return hmac.compare_digest(candidate, digest)
    return hmac.compare_digest(password.encode(), stored.encode())


def _secret_section(name: str) -> dict[str, Any]:
    """A secrets.toml section as a plain dict ({} when absent or no secrets file)."""
    try:
        section = st.secrets.get(name)
    except Exception:  # no secrets.toml at all
        return {}
    return dict(section) if section else {}


def _google_enabled() -> bool:
    return bool(_secret_section("auth"))


def _email_allowed(email: Optional[str]) -> bool:
    access = _secret_section("access")
    emails = {e.strip().lower() for e in access.get("allowed_emails", [])}
    domains = {d.strip().lower().lstrip("@") for d in access.get("allowed_domains", [])}
    if not emails and not domains:
        return False  # never let "any Google account" in by default
    email = (email or "").strip().lower()
    return email in emails or email.rsplit("@", 1)[-1] in domains


def current_user() -> Optional[str]:
    """The signed-in user's email/username, or None."""
    if st.session_state.get(PASSWORD_SESSION_KEY):
        return st.session_state[PASSWORD_SESSION_KEY]
    if _google_enabled() and st.user.get("is_logged_in", False):
        return st.user.get("email")
    return None


def _try_password_login() -> None:
    users = _secret_section("passwords")
    username = (st.session_state.get("_auth_username") or "").strip()
    password = st.session_state.get("_auth_password") or ""
    st.session_state["_auth_password"] = ""
    stored = users.get(username)
    if stored and verify_password(password, str(stored)):
        st.session_state[PASSWORD_SESSION_KEY] = username
        st.session_state.pop("_auth_error", None)
    else:
        time.sleep(1)  # slow down guessing
        st.session_state["_auth_error"] = "Incorrect username or password."


def _logout() -> None:
    if not st.session_state.pop(PASSWORD_SESSION_KEY, None):
        st.logout()


def _render_login(google: bool, passwords: bool) -> None:
    from core.theme import inject_global_css, render_page_header

    st.set_page_config(page_title="ArchitectureScope — Sign in", layout="centered")
    inject_global_css()
    render_page_header("Sign in to ArchitectureScope", "This workspace is private — sign in to continue.")

    if google:
        st.button("Sign in with Google", on_click=st.login, type="primary", use_container_width=True)
    if google and passwords:
        st.divider()
    if passwords:
        with st.form("password_login"):
            st.text_input("Username", key="_auth_username")
            st.text_input("Password", type="password", key="_auth_password")
            st.form_submit_button("Sign in", on_click=_try_password_login, use_container_width=True)
        if st.session_state.get("_auth_error"):
            st.error(st.session_state["_auth_error"])


def require_login() -> None:
    """Show the sign-in screen and stop the script unless a user is signed
    in and allowed. Adds the signed-in user + a sign-out button to the sidebar."""
    if os.environ.get("AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return

    google = _google_enabled()
    passwords = bool(_secret_section("passwords"))

    if not google and not passwords:
        st.set_page_config(page_title="ArchitectureScope — Sign in", layout="centered")
        st.error(
            "Sign-in isn't configured. Add an `[auth]` (Google) and/or `[passwords]` section to the "
            "app's secrets — see the README's Deployment section. For local development only, set "
            "`AUTH_DISABLED=1`."
        )
        st.stop()

    if st.session_state.get(PASSWORD_SESSION_KEY):
        user = st.session_state[PASSWORD_SESSION_KEY]
    elif google and st.user.get("is_logged_in", False):
        user = st.user.get("email")
        if not _email_allowed(user):
            st.set_page_config(page_title="ArchitectureScope — Sign in", layout="centered")
            st.error(f"{user} isn't authorized to use this app. Ask an administrator for access.")
            st.button("Sign out", on_click=st.logout)
            st.stop()
    else:
        _render_login(google, passwords)
        st.stop()

    with st.sidebar:
        st.caption(f"Signed in as **{user}**")
        st.button("Sign out", on_click=_logout, key="_auth_logout")


if __name__ == "__main__":
    import getpass

    print(hash_password(getpass.getpass("Password to hash: ")))
