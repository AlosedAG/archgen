"""Floating "Feedback" button (bottom-right of every page) that opens a
small chat: the user picks Bug / Idea / Question, types what happened,
attaches screenshots, and hits send — the feedback is emailed to the app
owner (see ``core/feedback.py``), with the page and the signed-in user
filled in automatically.

Rendered once per run from the router (``Home.py``), so it appears on
every page without each page having to call it.
"""

from __future__ import annotations

import logging
import os

import streamlit as st

from core.auth import _secret_section, current_user
from core.feedback import (
    ALLOWED_EXTENSIONS,
    DEFAULT_RECIPIENT,
    FEEDBACK_KINDS,
    MAX_ATTACHMENTS,
    Attachment,
    FeedbackError,
    build_message,
    load_settings,
    send,
)
from core.theme import ORANGE, ORANGE_HOVER

log = logging.getLogger(__name__)

HISTORY_KEY = "feedback_history"  # list of (role, markdown) chat bubbles for this session
TOAST_KEY = "feedback_toast"  # shown on the next run: a toast raised right before st.rerun() is lost
FAB_KEY = "feedback_fab"

# Pins the keyed container (Streamlit adds the class ``st-key-<key>``) to
# the bottom-right corner and styles its popover button as a round,
# branded action button. The chat panel itself opens above it.
_CSS = f"""
<style class="feedback-css">
/* Take both wrappers (this style block's and the button's) out of the page
   flow: as zero-height flex items they'd each still add a row gap above
   every page's content. */
[data-testid="stElementContainer"]:has(style.feedback-css),
[data-testid="stLayoutWrapper"]:has(> .st-key-{FAB_KEY}) {{
    position: absolute !important; width: 0; height: 0;
}}
.st-key-{FAB_KEY} {{
    position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 999990;
    width: auto !important;
}}
.st-key-{FAB_KEY} button[data-testid="stPopoverButton"] {{
    background: {ORANGE} !important; color: #FFFFFF !important; border: none !important;
    border-radius: 999px !important; padding: 0.55rem 1.15rem !important;
    box-shadow: 0 8px 22px rgba(42, 32, 88, 0.28); font-weight: 600;
}}
.st-key-{FAB_KEY} button[data-testid="stPopoverButton"]:hover {{ background: {ORANGE_HOVER} !important; }}
.st-key-{FAB_KEY} button[data-testid="stPopoverButton"] p {{ color: #FFFFFF !important; }}
div[data-testid="stPopoverBody"]:has(.st-key-feedback_panel) {{ width: min(420px, 92vw); }}
</style>
"""


def _settings():
    return load_settings({"feedback": _secret_section("feedback")}, os.environ)


def _say(role: str, text: str) -> None:
    st.session_state.setdefault(HISTORY_KEY, []).append((role, text))


def _handle_submission(submission, kind: str, page: str) -> None:
    text = (getattr(submission, "text", "") or "").strip()
    files = list(getattr(submission, "files", []) or [])
    attachments = [Attachment(f.name, f.getvalue()) for f in files]
    summary = text or "_(screenshots only)_"
    if attachments:
        summary += "\n\n" + "  \n".join(f":material/attach_file: {a.filename}" for a in attachments)
    _say("user", f"**{kind}** · {summary}")

    settings = _settings()
    if settings is None:
        _say(
            "assistant",
            f"Sending isn't switched on yet, sorry. Please email this to **{DEFAULT_RECIPIENT}** instead.",
        )
        return
    try:
        message = build_message(settings, kind=kind, text=text, page=page, user=current_user(), attachments=attachments)
        with st.spinner("Sending…"):
            send(settings, message)
    except FeedbackError as exc:
        log.warning("feedback not sent: %s", exc)
        _say("assistant", f":material/error: {exc}")
        return
    _say("assistant", ":material/check_circle: **Sent — thank you!** Aylin will follow up by email if needed.")
    st.session_state[TOAST_KEY] = True


def render_feedback_widget(page_title: str) -> None:
    """The floating button + chat panel. Safe to call on every run."""
    st.html(_CSS)  # style-only st.html is applied without taking up layout space
    if st.session_state.pop(TOAST_KEY, False):
        st.toast("Feedback sent — thank you!", icon=":material/check_circle:")
    with st.container(key=FAB_KEY):
        with st.popover("Feedback", icon=":material/chat:", help="Report a bug or share an idea"):
            with st.container(key="feedback_panel"):
                st.markdown("**Something not working? Have an idea?**")
                st.caption(
                    f"Tell us what happened and attach screenshots with the + button. "
                    f"It goes straight to Aylin — we add the page you're on ({page_title}) automatically."
                )
                kind = st.segmented_control(
                    "Type", FEEDBACK_KINDS, default=FEEDBACK_KINDS[0], key="feedback_kind", label_visibility="collapsed"
                )
                for role, content in st.session_state.get(HISTORY_KEY, []):
                    with st.chat_message(role, avatar=":material/support_agent:" if role == "assistant" else None):
                        st.markdown(content)
                submission = st.chat_input(
                    "Describe what happened…",
                    accept_file="multiple",
                    file_type=[ext.lstrip(".") for ext in ALLOWED_EXTENSIONS],
                    key="feedback_input",
                )
                st.caption(f"Up to {MAX_ATTACHMENTS} screenshots or PDFs.")
                if submission:
                    _handle_submission(submission, kind or FEEDBACK_KINDS[0], page_title)
                    st.rerun()
