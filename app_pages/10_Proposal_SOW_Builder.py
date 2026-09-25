"""Module 10 — Proposal & SOW Builder.

One tool that turns what's already known about a deal — the Written
Requirements Document and the Joint Evaluation Plan — into a seller's
proposal and/or Statement of Work, organized in the three areas a
proposal has to cover:

1. **Technical** — understanding of the problem, the proposed solution,
   and the tools, techniques and procedures used to implement it.
2. **Management** — team, governance, schedule, risks, acceptance.
3. **Cost** — milestone fees, optional add-ons, rate card, terms.

Scope gets its own tab and its own page in the PDF ("Scope at a Glance"):
every item is explicitly In Scope, Out of Scope, an Optional Add-on, or a
Client Responsibility, so the client can see what they can ask for and
what it costs to ask for more.

Every field is editable before generating the PDF. SonaMation boilerplate
(methodology, tools, governance, change control, terms) is pre-filled;
a proposal can be saved as .json and loaded back later, either as a
full copy or as a reusable template with the deal-specific parts removed.

State model: the whole proposal lives in one dict, ``prop_seed``. Widgets
are keyed with a revision number (``prop_rev``); any bulk change (import,
preset library, load file, reset) writes a new seed and bumps the
revision so every widget re-reads it. Bulk actions are applied at the end
of the script, after the current widget values are gathered, so an edit
made just before clicking an action button is never lost.
"""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import streamlit as st

from core.doc_export_ui import save_to_library_button
from core.proposal import (
    ADDON_LIBRARY,
    BILLING_OPTIONS,
    BLANK_ROWS,
    COVERAGE_NONE,
    DOCUMENT_TYPES,
    KPI_TYPES,
    OPTIONAL_SECTIONS,
    SCOPE_CLIENT,
    SCOPE_IN,
    SCOPE_LIBRARY,
    SCOPE_OPTIONAL,
    SCOPE_OUT,
    SCOPE_STATUSES,
    add_library_addons,
    add_library_items,
    as_template,
    default_proposal,
    format_money,
    from_json,
    import_from_jep,
    import_from_wrd,
    pricing_summary,
    requirement_coverage,
    scope_by_status,
    scope_from_requirements,
    to_bool,
    to_float,
    to_json,
    validate,
)
from core.proposal_pdf import proposal_to_pdf
from core.project_store import guess_project_name
from core.theme import BG_ALT, BORDER, ORANGE, PURPLE, PURPLE_LIGHT, TEXT_BODY, inject_global_css, render_page_header

st.set_page_config(page_title="Proposal & SOW Builder", layout="wide")
inject_global_css()
render_page_header(
    "Proposal & SOW Builder",
    "Build a seller's proposal and Statement of Work from the Requirements Document and Joint Evaluation "
    "Plan — technical approach, management approach, and cost — with a scope that states plainly what is "
    "included, what isn't, and what can be added. Everything is editable before the PDF is generated.",
)

# ---- State -------------------------------------------------------------------

if "prop_seed" not in st.session_state:
    seed = default_proposal()
    seed["client"]["company"] = guess_project_name()
    st.session_state["prop_seed"] = seed
st.session_state.setdefault("prop_rev", 0)
rev = st.session_state["prop_rev"]

# Streamlit drops a widget's state once a run doesn't render it (e.g. after
# visiting another page). When that's happened, rebuild the widgets from
# the last values gathered on this page instead of the older seed.
if f"prop_title_{rev}" not in st.session_state and "prop_current" in st.session_state:
    st.session_state["prop_seed"] = st.session_state["prop_current"]
seed: dict = st.session_state["prop_seed"]

actions: list[tuple[str, object]] = []  # applied at the end of the script


def _key(name: str) -> str:
    return f"prop_{name}_{rev}"


def _text(field: str, label: str, *, area: bool = False, height: int | None = None, help: str | None = None, placeholder: str | None = None) -> str:
    value = str(seed.get(field) or "")
    if area:
        return st.text_area(label, value=value, key=_key(field), height=height, help=help, placeholder=placeholder)
    return st.text_input(label, value=value, key=_key(field), help=help, placeholder=placeholder)


def _party(party: str, field: str, label: str) -> str:
    return st.text_input(label, value=str(seed.get(party, {}).get(field) or ""), key=_key(f"{party}_{field}"))


def _date(field: str, label: str) -> str:
    raw = str(seed.get(field) or "")
    try:
        value = date.fromisoformat(raw[:10]) if raw else None
    except ValueError:
        value = None
    picked = st.date_input(label, value=value, key=_key(field), format="YYYY-MM-DD")
    return picked.isoformat() if picked else ""


def _normalize(value, default):
    if isinstance(default, bool):
        return to_bool(value)
    if isinstance(default, float):
        return to_float(value)
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value)


def _table(field: str, *, column_config: dict | None = None, height: int | str = "auto") -> list[dict]:
    """A dynamic-rows data editor over one proposal table; returns its rows
    with the column types from ``BLANK_ROWS`` (money as float, flags as bool)."""
    template = BLANK_ROWS[field]
    rows = [{col: _normalize(r.get(col), d) for col, d in template.items()} for r in seed.get(field) or []]
    frame = pd.DataFrame(rows, columns=list(template))
    frame = frame.astype({col: (bool if isinstance(d, bool) else float if isinstance(d, float) else object) for col, d in template.items()})
    edited = st.data_editor(
        frame,
        key=_key(f"{field}_editor"),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=column_config or {},
        height=height,
    )
    return [{col: _normalize(rec.get(col), d) for col, d in template.items()} for rec in edited.to_dict("records")]


_WIDE = st.column_config.TextColumn(width="large")
_MONEY = st.column_config.NumberColumn(format="$%.2f", min_value=0.0)

proposal: dict = {"schema_version": seed.get("schema_version", 1)}

tab_setup, tab_tech, tab_scope, tab_mgmt, tab_cost, tab_review = st.tabs(
    ["1 · Setup", "2 · Technical", "3 · Scope", "4 · Management", "5 · Cost", "6 · Review & Generate"]
)

# ---- 1. Setup ----------------------------------------------------------------

with tab_setup:
    with st.container(border=True):
        st.markdown("**Start from existing work**")
        st.caption(
            "Imports are one-off merges: blank fields are filled and rows are appended, nothing you've typed "
            "here is overwritten. Requirements become the proposal's requirement list; the JEP's team, "
            "milestones and needs flow into Management and Technical."
        )
        wrd_snap = st.session_state.get("wrd_export_snapshot")
        jep_snap = st.session_state.get("jep_export_snapshot")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Import Requirements Document", disabled=not wrd_snap, use_container_width=True):
                actions.append(("import_wrd", wrd_snap))
            if not wrd_snap:
                st.caption("Open the Requirements Document page first in this session to enable.")
        with c2:
            if st.button("Import Joint Evaluation Plan", disabled=not jep_snap, use_container_width=True):
                actions.append(("import_jep", jep_snap))
            if not jep_snap:
                st.caption("Open the Joint Evaluation Plan page first in this session to enable.")
        with c3:
            if st.button("Reset to SonaMation defaults", type="secondary", use_container_width=True):
                actions.append(("reset", None))
        uploaded = st.file_uploader("Or load a saved proposal / template (.json)", type=["json"], key="prop_upload")
        if uploaded is not None and st.button("Load file"):
            actions.append(("load", uploaded.getvalue()))

    st.subheader("Document")
    c1, c2, c3 = st.columns([1.2, 2, 1])
    with c1:
        doc_type = seed.get("document_type") if seed.get("document_type") in DOCUMENT_TYPES else DOCUMENT_TYPES[0]
        proposal["document_type"] = st.selectbox("Document type", DOCUMENT_TYPES, index=DOCUMENT_TYPES.index(doc_type), key=_key("document_type"))
    with c2:
        proposal["title"] = _text("title", "Engagement title")
    with c3:
        proposal["reference_number"] = _text("reference_number", "Reference / SOW number")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        proposal["issue_date"] = _date("issue_date", "Issue date")
    with c2:
        proposal["effective_date"] = _date("effective_date", "Effective date")
    with c3:
        proposal["expiration_date"] = _date("expiration_date", "Expiration date")
    with c4:
        proposal["valid_until"] = _date("valid_until", "Proposal valid until")

    st.subheader("Addresses and contacts for notices")
    fields = [("company", "Company"), ("contact", "Primary contact"), ("address", "Address"), ("phone", "Phone"), ("email", "Email")]
    c1, c2 = st.columns(2)
    for col, party, heading in ((c1, "client", "Client"), (c2, "seller", "SonaMation")):
        with col:
            st.markdown(f"**{heading}**")
            proposal[party] = {f: _party(party, f, label) for f, label in fields}

    st.subheader("Introduction")
    proposal["executive_summary"] = _text(
        "executive_summary", "Executive summary", area=True, height=120,
        placeholder="Two or three sentences: the client's problem, what SonaMation will deliver, and the outcome.",
    )
    proposal["company_overview"] = _text("company_overview", "About SonaMation (standard text)", area=True, height=110)

# ---- 2. Technical ------------------------------------------------------------

with tab_tech:
    st.info(
        "**Volume I — Technical Approach.** Show that SonaMation understands the problem, and exactly how it "
        "will be solved: the tools, techniques and procedures used to implement it."
    )
    proposal["problem_statement"] = _text(
        "problem_statement", "1.1 Understanding of the problem", area=True, height=130,
        help="Start lines with '- ' for bullets in the PDF.",
    )
    proposal["current_state"] = _text("current_state", "Current state (optional)", area=True, height=90)
    st.markdown("**1.2 Objectives**")
    proposal["objectives"] = _table("objectives", column_config={"Objective": _WIDE})
    st.markdown("**1.3 Requirements**")
    st.caption("IDs (R-01, R-02...) are assigned automatically if left blank; scope items cite them in the Scope tab.")
    proposal["requirements"] = _table(
        "requirements",
        column_config={
            "Requirement": _WIDE,
            "Priority": st.column_config.SelectboxColumn(options=["Must Have", "Should Have", "Nice to Have", "To Confirm"]),
        },
    )
    proposal["solution_overview"] = _text(
        "solution_overview", "1.4 Proposed solution", area=True, height=150,
        help="How the requirements will be met. Start lines with '- ' for bullets.",
    )
    st.markdown("**1.5 Methodology**")
    proposal["methodology"] = _table("methodology", column_config={"Activities": _WIDE, "Outputs": _WIDE})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**1.6 Tools & platforms**")
        proposal["tools"] = _table(
            "tools", column_config={"Provided By": st.column_config.SelectboxColumn(options=["SonaMation", "Client", "Third Party"])}
        )
    with c2:
        st.markdown("**1.7 Techniques & procedures**")
        proposal["techniques"] = _table("techniques", column_config={"How It Is Applied": _WIDE})
    st.markdown("**Glossary of terms**")
    proposal["glossary"] = _table("glossary", column_config={"Definition": _WIDE})

# ---- 3. Scope ----------------------------------------------------------------

_BUCKET_COLORS = {SCOPE_IN: PURPLE, SCOPE_OUT: "#6E6980", SCOPE_OPTIONAL: ORANGE, SCOPE_CLIENT: PURPLE_LIGHT}
_BUCKET_HINTS = {
    SCOPE_IN: "Delivered, up to the stated limit.",
    SCOPE_OUT: "Not included — only via Change Request.",
    SCOPE_OPTIONAL: "Pre-priced; client can add any time.",
    SCOPE_CLIENT: "The client provides this.",
}

with tab_scope:
    st.info(
        "**Scope is the section clients misread most.** Put every item a client might ask about into exactly "
        "one bucket. Give each In Scope item a quantity limit and acceptance criteria, and list common "
        "requests you are *not* doing as Out of Scope — that's what prevents disputes later."
    )
    with st.expander("Add items from the preset libraries", expanded=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            picked = st.multiselect(
                "Common deliverables (already phrased with limits and acceptance criteria)",
                [entry["Item"] for entry in SCOPE_LIBRARY],
                key=_key("library_pick"),
            )
        with c2:
            picked_status = st.selectbox("Add as", SCOPE_STATUSES, key=_key("library_status"))
        if st.button("Add deliverables to scope", disabled=not picked):
            actions.append(("add_items", (picked, picked_status)))
        picked_addons = st.multiselect(
            "Add-on services (added to the Cost volume's menu and listed in scope as Optional Add-ons)",
            [entry["Service"] for entry in ADDON_LIBRARY],
            key=_key("addon_pick"),
        )
        if st.button("Add services to add-on menu", disabled=not picked_addons):
            actions.append(("add_addons", picked_addons))
    if st.button("Draft a scope item for every requirement not yet covered"):
        actions.append(("draft_scope", None))

    st.markdown("**Scope items**")
    st.caption(
        "IDs (S-01, S-02...) are assigned automatically. 'Req. ID' links an item to the requirements it "
        "satisfies (comma-separated, e.g. R-01, R-03)."
    )
    proposal["scope"] = _table(
        "scope",
        column_config={
            "Status": st.column_config.SelectboxColumn(options=SCOPE_STATUSES, required=True),
            "Item": _WIDE,
            "Acceptance Criteria": _WIDE,
            "Tools / Techniques": st.column_config.TextColumn(width="medium"),
        },
        height=380,
    )

    st.markdown("#### Preview — Scope at a Glance")
    groups = scope_by_status({"scope": proposal["scope"]})
    cols = st.columns(4)
    for col, status in zip(cols, SCOPE_STATUSES):
        items = groups[status]
        lines = "".join(
            f"<li><b>{html.escape(i['ID'])}</b> {html.escape(i['Item'])}"
            + (f"<br><span style='color:#8a859c;font-size:0.8rem'>{html.escape(i['Quantity / Limit'])}</span>" if i.get("Quantity / Limit") else "")
            + "</li>"
            for i in items
        ) or "<li style='color:#8a859c'>Nothing listed</li>"
        with col:
            st.markdown(
                f"""<div style="border:1px solid {BORDER};border-radius:12px;overflow:hidden;height:100%">
                <div style="background:{_BUCKET_COLORS[status]};color:white;padding:0.5rem 0.8rem;font-weight:700">
                {html.escape(status)} ({len(items)})<div style="font-weight:400;font-size:0.78rem;opacity:0.9">{_BUCKET_HINTS[status]}</div></div>
                <ul style="background:{BG_ALT};margin:0;padding:0.6rem 0.8rem 0.6rem 1.8rem;color:{TEXT_BODY};font-size:0.88rem">{lines}</ul></div>""",
                unsafe_allow_html=True,
            )

    st.markdown("#### Requirements coverage")
    coverage = requirement_coverage({"requirements": proposal["requirements"], "scope": proposal["scope"]})
    if coverage:
        st.dataframe(pd.DataFrame(coverage), hide_index=True, use_container_width=True)
        gaps = [r["ID"] for r in coverage if r["Coverage"] == COVERAGE_NONE]
        if gaps:
            st.warning(
                f"Not addressed by any scope item: {', '.join(gaps)}. Put that requirement ID in the 'Req. ID' "
                "column of the In Scope item that delivers it — or, if you're not doing it, of an Out of Scope "
                "item so the exclusion is stated explicitly."
            )
        else:
            st.success("Every requirement is addressed by a scope item.")
    else:
        st.caption("Add requirements in the Technical tab to check coverage here.")

    st.markdown("**Assumptions**")
    proposal["assumptions"] = _table("assumptions", column_config={"Assumption": _WIDE})
    proposal["change_process"] = _text("change_process", "Change Request process (standard text)", area=True, height=120)

# ---- 4. Management -----------------------------------------------------------

with tab_mgmt:
    st.info("**Volume II — Management Approach.** How SonaMation will manage contract performance.")
    st.markdown("**2.1 Project team & roles**")
    proposal["team"] = _table(
        "team",
        column_config={
            "Side": st.column_config.SelectboxColumn(options=["SonaMation", "Client", "Third Party"]),
            "Responsibilities": _WIDE,
        },
    )
    st.markdown("**2.2 Governance & communication**")
    proposal["governance"] = _table("governance", column_config={"Purpose": _WIDE})
    st.markdown("**2.3 Schedule**")
    proposal["timeline"] = _table("timeline", column_config={"Key Deliverables": _WIDE})
    st.markdown("**Risk management**")
    levels = st.column_config.SelectboxColumn(options=["Low", "Medium", "High"])
    proposal["risks"] = _table("risks", column_config={"Likelihood": levels, "Impact": levels, "Mitigation": _WIDE})
    st.markdown("**Targeted KPIs**")
    st.caption("Primary: value drivers tied to ROI. Secondary: operational/marketing improvement.")
    proposal["kpis"] = _table("kpis", column_config={"Type": st.column_config.SelectboxColumn(options=KPI_TYPES), "Definition": _WIDE})
    proposal["acceptance_process"] = _text("acceptance_process", "Acceptance process (standard text)", area=True, height=110)

# ---- 5. Cost -----------------------------------------------------------------

with tab_cost:
    st.info("**Volume III — Cost & Pricing.** Milestone fees, the add-on menu, and the rate for anything beyond scope.")
    c1, c2 = st.columns([1, 3])
    with c1:
        currencies = ["USD", "CAD", "MXN", "EUR", "GBP"]
        current = seed.get("currency") if seed.get("currency") in currencies else "USD"
        proposal["currency"] = st.selectbox("Currency", currencies, index=currencies.index(current), key=_key("currency"))
    st.markdown("**3.1 Deliverables & milestone schedule**")
    st.caption("Mirrors the SOW milestone table: what's delivered, when it can start, when it's due, and the fee due on acceptance.")
    proposal["milestones"] = _table("milestones", column_config={"Deliverables": _WIDE, "Fee": _MONEY})
    st.markdown("**Optional add-on services menu**")
    st.caption("Tick 'Add to Total' for add-ons the client has already chosen.")
    proposal["addons"] = _table(
        "addons",
        column_config={"Includes": _WIDE, "Cost": _MONEY, "Billing": st.column_config.SelectboxColumn(options=BILLING_OPTIONS)},
    )
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("**Rate card (for Change Requests)**")
        proposal["rate_card"] = _table("rate_card", column_config={"Hourly Rate": _MONEY})
    with c2:
        proposal["discount_pct"] = st.number_input(
            "Discount (%)", min_value=0.0, max_value=100.0, step=1.0, value=to_float(seed.get("discount_pct")), key=_key("discount_pct")
        )
    totals = pricing_summary(proposal)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Milestone fees", format_money(totals["milestone_total"], proposal["currency"]))
    m2.metric("Selected add-ons (one-time)", format_money(totals["selected_addons_one_time"], proposal["currency"]))
    m3.metric("Discount", format_money(-totals["discount"], proposal["currency"]))
    m4.metric("Total one-time fee", format_money(totals["total"], proposal["currency"]))
    for billing, amount in totals["recurring"].items():
        st.caption(f"Plus selected recurring add-ons: {format_money(amount, proposal['currency'])} ({billing}).")
    proposal["payment_terms"] = _text("payment_terms", "Payment terms (standard text)", area=True, height=100)
    proposal["expenses"] = _text("expenses", "Expenses (standard text)", area=True, height=90)
    proposal["confidentiality"] = _text("confidentiality", "Confidentiality (standard text)", area=True, height=80)

# ---- 6. Review & generate ----------------------------------------------------

with tab_review:
    st.markdown("**Sections to include**")
    st.caption("The cover, Scope at a Glance, and the Technical, Management and Cost volumes are always included.")
    toggle_cols = st.columns(4)
    seed_sections = seed.get("sections", {})
    proposal["sections"] = {}
    for i, (key, label) in enumerate(OPTIONAL_SECTIONS.items()):
        with toggle_cols[i % 4]:
            proposal["sections"][key] = st.checkbox(label, value=bool(seed_sections.get(key, True)), key=_key(f"section_{key}"))

    st.session_state["prop_current"] = proposal

    groups = scope_by_status(proposal)
    totals = pricing_summary(proposal)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("In scope", len(groups[SCOPE_IN]))
    m2.metric("Out of scope", len(groups[SCOPE_OUT]))
    m3.metric("Optional add-ons", len(groups[SCOPE_OPTIONAL]))
    m4.metric("Total one-time fee", format_money(totals["total"], proposal["currency"]))

    warnings = validate(proposal)
    if warnings:
        st.warning("**Before sending, check:**\n\n" + "\n".join(f"- {w}" for w in warnings))
    else:
        st.success("No gaps found — scope, requirements and pricing all line up.")

    client_name = proposal["client"].get("company") or ""
    project_name = client_name or proposal.get("title") or ""
    stub = f"{client_name or 'Client'}_{proposal['document_type']}".replace(" ", "_").replace("+", "and")
    try:
        pdf_bytes = proposal_to_pdf(proposal)
    except Exception as exc:  # keep the editor usable even if one field trips the renderer
        pdf_bytes = None
        st.error(f"Couldn't build the PDF: {exc}")

    st.subheader("Export")
    c1, c2, c3 = st.columns(3)
    with c1:
        if pdf_bytes:
            st.download_button("Download PDF", data=pdf_bytes, file_name=f"{stub}.pdf", mime="application/pdf", use_container_width=True)
    with c2:
        st.download_button(
            "Download editable copy (.json)", data=to_json(proposal), file_name=f"{stub}.json", mime="application/json", use_container_width=True
        )
    with c3:
        st.download_button(
            "Download as reusable template (.json)",
            data=to_json(as_template(proposal)),
            file_name="SonaMation_proposal_template.json",
            mime="application/json",
            use_container_width=True,
        )
    st.caption(
        "The .json copy loads back into this builder (Setup tab) to keep editing. The template keeps only the "
        "reusable parts — SonaMation details, methodology, tools, governance, add-on menu, rate card, standard "
        "terms — so the next proposal starts from your house style."
    )
    artifacts: dict[str, bytes | str] = {"json": to_json(proposal)}
    if pdf_bytes:
        artifacts["pdf"] = pdf_bytes
    save_to_library_button(artifacts, document_type="Proposal & SOW", project_name=project_name)

# ---- Bulk actions (after gathering, so no in-flight edit is lost) ------------

if actions:
    action, payload = actions[0]
    new = proposal
    try:
        if action == "import_wrd":
            new = import_from_wrd(proposal, payload["sections"])
            if not new["client"].get("company") and payload.get("project_name"):
                new["client"]["company"] = payload["project_name"]
        elif action == "import_jep":
            new = import_from_jep(proposal, payload["sections"], payload.get("project_name", ""))
        elif action == "reset":
            new = default_proposal()
        elif action == "load":
            new = from_json(payload)
        elif action == "add_items":
            items, status = payload
            new = add_library_items(proposal, items, status)
        elif action == "add_addons":
            new = add_library_addons(proposal, payload)
        elif action == "draft_scope":
            new = scope_from_requirements(proposal)
    except (ValueError, KeyError) as exc:
        st.error(f"Couldn't apply that: {exc}")
    else:
        st.session_state["prop_seed"] = new
        st.session_state["prop_current"] = new
        st.session_state["prop_rev"] = rev + 1
        st.rerun()
