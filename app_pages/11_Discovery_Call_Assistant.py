"""Module 11 — Discovery Call Assistant (AI-assisted).

Filled in live during a client discovery call: the specialist jots raw,
shorthand notes against the standard discovery questions (Goals, Data,
Processes, Solutions Design), then Claude turns them into either

- a structured **business-analysis** document (with every blank answer
  surfaced as a follow-up gap, never guessed), or
- a plain-language **client explainer** of the HubSpot hubs in play.

The only module that calls an external AI service; it needs an Anthropic
API key (Setup page, or ``ANTHROPIC_API_KEY``). Notes themselves are typed
and kept locally with no key at all — only the Generate buttons need one.

Questions, their input type (dropdown / multiselect / radio / text), and
their options come from ``config/discovery_options.yaml`` — edit that, not
this page, to change what's asked. Each choice question also gets an
"Other (specify)" box, a shorthand notes line, and a "Flag for follow-up"
checkbox.

Every note field's value lives under a ``disc_*`` session key, which the
router (Home.py) re-saves on every run so notes survive switching pages
mid-call.
"""

from __future__ import annotations

import json
from datetime import date

import anthropic
import streamlit as st

from core.connections import SETUP_URL, get_anthropic_key
from core.discovery import (
    HUBSPOT_MODULES,
    DiscoveryError,
    answered_count,
    build_business_analysis_input,
    build_client_explainer_input,
    flagged_keys,
    has_any_notes,
    question_bank,
    stream_document,
    suggest_modules,
)
from core.discovery_config import INPUT_MULTISELECT, INPUT_SELECT, DiscoveryConfigError, Question
from core.doc_export_ui import render_export_footer
from core.exporters import markdown_to_docx, markdown_to_pdf
from core.project_store import project_name_input
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Discovery Call Assistant", layout="wide")
inject_global_css()
render_page_header(
    "Discovery Call Assistant",
    "Type notes live during the discovery call — shorthand is fine, blanks are fine. When the call "
    "ends, generate a clean business-analysis document (with every gap listed as a follow-up "
    "question) and a plain-language explainer of the HubSpot hubs the client needs.",
)

BA_OUTPUT_KEY = "disc_ba_output"
CE_OUTPUT_KEY = "disc_ce_output"
CE_MODULES_KEY = "disc_ce_modules"
BUSINESS_TYPE_KEY = "disc_business_type"


try:
    BANK = question_bank()
except DiscoveryConfigError as exc:
    st.error(
        f"The discovery question bank (`config/{exc.path.name}`) has errors, so the form can't be shown. "
        "Fix these entries and refresh the page:"
    )
    st.markdown("\n".join(f"- {problem}" for problem in exc.problems))
    st.stop()
SECTIONS = BANK.sections


def _field_key(section: str, field: str) -> str:
    return f"disc_{section.lower().replace(' ', '_')}_{field}"


def _part_key(section: str, question: Question, part: str) -> str:
    """Session key for a question's companion widget: ``other`` (the
    "Other (specify)" text), ``notes``, or ``flag``. Double underscore so
    it can't collide with a question id (ids are single-underscore)."""
    return f"{_field_key(section, question.key)}__{part}"


def _question_keys(section: str, question: Question) -> list[str]:
    """Every session key one question's answer is spread across. A text
    question's answer lives in its main key, so it has no notes/other."""
    keys = [_field_key(section, question.key), _part_key(section, question, "flag")]
    if question.is_choice:
        keys += [_part_key(section, question, "other"), _part_key(section, question, "notes")]
    return keys


def _all_note_keys() -> list[str]:
    keys = [BUSINESS_TYPE_KEY]
    for section, questions in SECTIONS.items():
        for q in questions:
            keys += _question_keys(section, q)
        keys += [_field_key(section, "notes"), _field_key(section, "edge_cases")]
    return keys


def _collect_answer(section: str, question: Question) -> dict:
    """One question's widgets, read back as a structured answer (see
    :func:`core.discovery.empty_answer`)."""
    value = st.session_state.get(_field_key(section, question.key))
    flagged = bool(st.session_state.get(_part_key(section, question, "flag"), False))
    if not question.is_choice:
        return {"selected": [], "other": "", "notes": str(value or ""), "flagged": flagged}
    return {
        "selected": list(value) if isinstance(value, list) else ([value] if value else []),
        "other": st.session_state.get(_part_key(section, question, "other"), ""),
        "notes": st.session_state.get(_part_key(section, question, "notes"), ""),
        "flagged": flagged,
    }


def _collect_notes() -> dict:
    return {
        section: {
            "answers": {q.key: _collect_answer(section, q) for q in questions},
            "notes": st.session_state.get(_field_key(section, "notes"), ""),
            "edge_cases": st.session_state.get(_field_key(section, "edge_cases"), ""),
        }
        for section, questions in SECTIONS.items()
    }


def _append_text(key: str, text: str) -> None:
    existing = str(st.session_state.get(key, "") or "").strip()
    st.session_state[key] = f"{existing}; {text}" if existing else text


def _sanitize_choice_state(section: str, question: Question) -> None:
    """Make a choice question's stored value safe to hand to its widget
    (Streamlit raises on a value that isn't among the options), without
    losing anything the specialist typed:

    - free text from a backup saved before the question had options
      moves into the question's notes;
    - selections no longer in the YAML (an option was renamed/removed)
      move into the "Other (specify)" text;
    - extra selections when a multiselect became a single select move
      into notes.
    """
    key = _field_key(section, question.key)
    if key not in st.session_state:
        return
    value = st.session_state[key]
    choices = BANK.choices(question)
    if isinstance(value, str) and value.strip() and value not in choices:
        _append_text(_part_key(section, question, "notes"), value.strip())
        value = None
    items = list(value) if isinstance(value, (list, tuple)) else ([value] if value else [])
    valid = [v for v in items if v in choices]
    stale = [str(v) for v in items if v not in choices and str(v).strip()]
    if stale:
        _append_text(_part_key(section, question, "other"), "; ".join(stale))
        if BANK.other_option not in valid:
            valid.append(BANK.other_option)
    if question.input == INPUT_MULTISELECT:
        cleaned = valid
    else:
        cleaned = valid[0] if valid else None
        if len(valid) > 1:
            _append_text(_part_key(section, question, "notes"), "; ".join(valid[1:]))
    if cleaned != st.session_state[key]:
        st.session_state[key] = cleaned


def _load_notes_backup() -> None:
    uploaded = st.session_state.get("discbtn_upload")
    if uploaded is None:
        return
    try:
        data = json.loads(uploaded.getvalue().decode("utf-8"))
        fields = data.get("fields", {})
    except (ValueError, AttributeError):
        st.session_state["disc_upload_error"] = "That file isn't a notes backup from this page."
        return
    choice_keys = {_field_key(s, q.key) for s, qs in SECTIONS.items() for q in qs if q.is_choice}
    valid = set(_all_note_keys())
    for key, value in fields.items():
        if key not in valid:
            continue
        if key.endswith("__flag"):
            st.session_state[key] = bool(value)
        elif key in choice_keys:
            # Left as saved (list, single option, or a pre-dropdown free-text
            # answer) — _sanitize_choice_state fits it to the widget.
            st.session_state[key] = value
        else:
            st.session_state[key] = str(value or "")
    if data.get("project_name"):
        st.session_state["report_project_name"] = data["project_name"]
    st.session_state.pop("disc_upload_error", None)


def _reset_call() -> None:
    for key in [k for k in st.session_state.keys() if str(k).startswith("disc_")]:
        del st.session_state[key]


def _use_recommended_modules() -> None:
    st.session_state[CE_MODULES_KEY] = suggest_modules(st.session_state.get(BA_OUTPUT_KEY, ""))


def _generate(payload: dict, output_key: str) -> None:
    """Stream a document into the page, then store it and rerun so the
    result renders in its normal preview/edit layout."""
    client = anthropic.Anthropic(api_key=get_anthropic_key())
    try:
        with st.container(border=True):
            text = st.write_stream(stream_document(client, payload))
    except DiscoveryError as exc:
        st.error(str(exc))
        return
    except anthropic.AuthenticationError:
        st.error(f"The Anthropic API key was rejected. Check it on [Setup & API keys]({SETUP_URL}).")
        return
    except anthropic.PermissionDeniedError:
        st.error("This Anthropic API key doesn't have access to the model. Check the key's workspace permissions.")
        return
    except anthropic.RateLimitError:
        st.error("Anthropic rate limit reached. Wait a minute and try again.")
        return
    except anthropic.APIConnectionError:
        st.error("Couldn't reach the Anthropic API. Check your internet connection and try again.")
        return
    except anthropic.APIStatusError as exc:
        st.error(f"Anthropic API error ({exc.status_code}): {exc.message}")
        return
    st.session_state[output_key] = text if isinstance(text, str) else "".join(map(str, text))
    st.rerun()


def _render_question(section: str, question: Question) -> None:
    """One question card: the dropdown/multiselect/radio from the YAML
    (or a text box for text questions), an "Other — specify" box when the
    fallback option is picked, a shorthand notes line, and the follow-up flag."""
    key = _field_key(section, question.key)
    help_text = question.hint or None
    with st.container(border=True):
        if not question.is_choice:
            st.text_area(question.label, key=key, height=90, help=help_text, placeholder="Shorthand is fine")
        else:
            _sanitize_choice_state(section, question)
            choices = BANK.choices(question)
            # index=None: nothing pre-selected — an unanswered question must
            # stay blank so it's reported as a gap, not as the first option.
            if question.input == INPUT_MULTISELECT:
                picked = st.multiselect(
                    question.label, choices, key=key, help=help_text, placeholder="Choose all that apply"
                )
            elif question.input == INPUT_SELECT:
                picked = st.selectbox(
                    question.label, choices, index=None, key=key, help=help_text, placeholder="Choose one"
                )
            else:
                picked = st.radio(question.label, choices, index=None, key=key, help=help_text, horizontal=True)
            if BANK.other_option in (picked if isinstance(picked, list) else [picked]):
                st.text_input(
                    "Other — specify",
                    key=_part_key(section, question, "other"),
                    placeholder="What did they say?",
                )
            st.text_input(
                f"Notes — {question.label}",
                key=_part_key(section, question, "notes"),
                placeholder="Notes / shorthand",
                label_visibility="collapsed",
            )
        st.checkbox("⚑ Flag for follow-up", key=_part_key(section, question, "flag"))


def _render_flagged_summary(notes: dict) -> None:
    """Every question flagged for follow-up, across all sections — the
    specialist's to-revisit list before the call ends."""
    flagged = [
        (section, q.label)
        for section, questions in SECTIONS.items()
        for q in questions
        if q.key in flagged_keys(notes[section])
    ]
    if not flagged:
        return
    with st.container(border=True):
        st.markdown(f"**⚑ Flagged for follow-up ({len(flagged)})**")
        st.markdown("\n".join(f"- **{section}** — {label}" for section, label in flagged))
        st.caption("Flagged questions are sent with your notes as items to confirm before scoping.")


def _render_result(output_key: str, *, doc_title: str, document_type: str, file_suffix: str) -> None:
    text = st.session_state.get(output_key, "")
    if not text:
        return
    st.divider()
    preview_tab, edit_tab = st.tabs(["Preview", "Edit text"])
    with edit_tab:
        st.caption("Correct anything before exporting — downloads use this text.")
        st.text_area("Document (Markdown)", key=output_key, height=500, label_visibility="collapsed")
    with preview_tab:
        st.markdown(st.session_state[output_key])
    final = st.session_state[output_key]
    project_name = st.session_state.get("report_project_name", "")
    stub = f"{project_name or 'client'}_{file_suffix}".replace(" ", "_")
    render_export_footer(
        {
            "docx": markdown_to_docx(final, title=doc_title).getvalue(),
            "pdf": markdown_to_pdf(final, title=doc_title),
            "md": final,
        },
        document_type=document_type,
        project_name=project_name,
        file_stub=stub,
    )


# ---- Header inputs --------------------------------------------------------

api_key = get_anthropic_key()
if not api_key:
    st.warning(
        f"No Anthropic API key yet — you can take notes now, but generating documents needs one. "
        f"Add it on [Setup & API keys]({SETUP_URL})."
    )

name_col, type_col = st.columns(2)
with name_col:
    project_name_input(label="Client / project name")
with type_col:
    st.text_input(
        "Client's business type",
        key=BUSINESS_TYPE_KEY,
        placeholder="e.g. multi-location dental practice",
        help="Used to tailor the client explainer with one example specific to their business.",
    )

ba_tab, ce_tab = st.tabs(["1 · Business analysis (during the call)", "2 · Client explainer (share with the client)"])

# ---- Mode 1: business analysis -------------------------------------------

with ba_tab:
    st.caption(
        "Answer what you can, in any order. Anything left blank becomes a specific follow-up "
        "question in the generated document — nothing is guessed."
    )
    # Static tab labels: a label that changed as answers were typed (e.g. a
    # live "3/5" count) would make Streamlit reset to the first tab mid-call.
    section_tabs = st.tabs(list(SECTIONS))
    progress_notes = _collect_notes()
    for tab, (section, questions) in zip(section_tabs, SECTIONS.items()):
        with tab:
            flag_count = len(flagged_keys(progress_notes[section]))
            st.caption(
                f"{answered_count(progress_notes[section])} of {len(questions)} questions answered"
                + (f" · ⚑ {flag_count} flagged for follow-up" if flag_count else "")
            )
            cols = st.columns(2)
            for i, question in enumerate(questions):
                with cols[i % 2]:
                    _render_question(section, question)
            notes_col, edge_col = st.columns(2)
            with notes_col:
                st.text_area(
                    f"Other {section.lower()} notes",
                    key=_field_key(section, "notes"),
                    height=110,
                    placeholder="Anything said that doesn't fit a question above",
                )
            with edge_col:
                st.text_area(
                    "Edge cases / flags",
                    key=_field_key(section, "edge_cases"),
                    height=110,
                    placeholder="Compliance, multi-location, multi-entity, contradictions…",
                )

    notes = _collect_notes()
    _render_flagged_summary(notes)
    can_generate = bool(api_key) and has_any_notes(notes)
    if st.button(
        "Generate business analysis",
        type="primary",
        disabled=not can_generate,
        key="discbtn_generate_ba",
    ):
        _generate(
            build_business_analysis_input(
                notes,
                client_name=st.session_state.get("report_project_name", ""),
                business_type=st.session_state.get(BUSINESS_TYPE_KEY, ""),
            ),
            BA_OUTPUT_KEY,
        )
    if api_key and not has_any_notes(notes):
        st.caption("Capture at least one answer or note to enable generating.")

    _render_result(
        BA_OUTPUT_KEY,
        doc_title=f"Discovery Business Analysis — {st.session_state.get('report_project_name') or 'Client'}",
        document_type="Discovery Business Analysis",
        file_suffix="discovery_business_analysis",
    )

    with st.expander("Back up, restore, or reset call notes"):
        st.caption(
            "Notes live only in this browser session. Download a backup mid-call if you're worried "
            "about closing the tab; load it back here to pick up where you left off."
        )
        backup = {
            "project_name": st.session_state.get("report_project_name", ""),
            "saved_on": date.today().isoformat(),
            "fields": {k: st.session_state[k] for k in _all_note_keys() if k in st.session_state},
        }
        st.download_button(
            "Download notes backup (.json)",
            data=json.dumps(backup, indent=2),
            file_name=f"{(backup['project_name'] or 'client').replace(' ', '_')}_discovery_notes.json",
            mime="application/json",
            key="discbtn_backup",
        )
        st.file_uploader("Restore a notes backup", type=["json"], key="discbtn_upload", on_change=_load_notes_backup)
        if st.session_state.get("disc_upload_error"):
            st.error(st.session_state["disc_upload_error"])
        st.button(
            "Start a new call (clear all notes and drafts)",
            type="secondary",
            on_click=_reset_call,
            key="discbtn_reset",
        )

# ---- Mode 2: client explainer ---------------------------------------------

with ce_tab:
    st.caption(
        "A short, jargon-free explainer of each HubSpot hub you select — written for a client who "
        "has never used HubSpot, so they can decide what they want."
    )
    st.session_state.setdefault(CE_MODULES_KEY, suggest_modules(st.session_state.get(BA_OUTPUT_KEY, "")))
    st.multiselect("HubSpot hubs to explain", HUBSPOT_MODULES, key=CE_MODULES_KEY)
    if st.session_state.get(BA_OUTPUT_KEY):
        st.button(
            "Use the hubs recommended in the business analysis",
            type="secondary",
            on_click=_use_recommended_modules,
            key="discbtn_use_recommended",
        )
    selected = st.session_state.get(CE_MODULES_KEY, [])
    if st.button(
        "Generate client explainer",
        type="primary",
        disabled=not (api_key and selected),
        key="discbtn_generate_ce",
    ):
        _generate(
            build_client_explainer_input(selected, business_type=st.session_state.get(BUSINESS_TYPE_KEY, "")),
            CE_OUTPUT_KEY,
        )
    _render_result(
        CE_OUTPUT_KEY,
        doc_title="Your HubSpot Options, Explained",
        document_type="Discovery Client Explainer",
        file_suffix="hubspot_explainer",
    )
