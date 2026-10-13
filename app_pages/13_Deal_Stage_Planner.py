"""Deal Stage Planner — pre-call template out, filled-out planner in.

1. **Pre-call templates**: download the HubSpot Deal Stage Planner (.xlsx)
   to send to the client before the call, or save it to the Project Library.
2. **Import**: upload the client's filled-out planner. It's parsed
   (``archscope_domain.stage_planner``), shown for review and editing, and
   only applied — to the Discovery Call Assistant, the Architecture
   Generator and the build order — when the specialist clicks Apply, with
   an explicit confirmation before replacing anything already there.

The template's layout and the mapping rules live in
``packages/domain/src/archscope_domain/config/stage_planner.yaml``.
Input ingestion only: nothing here talks to HubSpot.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd
import streamlit as st

from archscope_domain.discovery_build_order import BuildOrderConfig
from archscope_domain.discovery import discovery_build_order
from archscope_domain.discovery_config import DiscoveryConfigError
from archscope_domain.stage_planner import (
    PlannedStage,
    StagePlanner,
    StagePlannerParseError,
    build_template,
    merge_notes,
    parse_stage_planner,
    to_build_items,
    to_deal_properties,
    to_discovery_answer,
    to_discovery_notes,
    to_pipeline,
    to_workflows,
)
from core.doc_export_ui import render_export_footer
from core.project_store import project_name_input
from core.stage_planner_session import (
    APPLIED_KEY,
    TARGET_ARCHITECTURE,
    TARGET_DISCOVERY,
    TARGETS,
    applied_record,
    planner_config,
)
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Deal Stage Planner", layout="wide")
inject_global_css()
render_page_header(
    "Deal Stage Planner",
    "Send the client the Deal Stage Planner before the call. When it comes back filled in, import it here, "
    "review what was read, and apply it to discovery, the architecture, and the build order.",
)

DRAFT_KEY = "spl_draft"  # parsed (then edited) planner awaiting review — not applied anywhere
DRAFT_HASH_KEY = "spl_draft_hash"

try:
    CONFIG = planner_config()
    BUILD: BuildOrderConfig = discovery_build_order()
except DiscoveryConfigError as exc:
    st.error(f"`config/{exc.path.name}` has errors, so the Stage Planner can't be used. Fix these entries and refresh:")
    st.markdown("\n".join(f"- {problem}" for problem in exc.problems))
    st.stop()


def _field_key(section: str, field: str) -> str:
    """The Discovery Call Assistant's session key for a section field (see its ``_field_key``)."""
    return f"disc_{section.lower().replace(' ', '_')}_{field}"


ANSWER_KEY = _field_key(CONFIG.discovery_section, CONFIG.discovery_question_id)
NOTES_KEY = _field_key(CONFIG.discovery_section, "notes")

# Pre-call templates the specialist can send. One for now; each entry is
# (description, file stub, builder).
PRECALL_TEMPLATES = {
    CONFIG.template["title"]: (
        "Each column is a pipeline stage: forecast %, entry / exit criteria, desired actions, automations, "
        "and the deal properties required at that stage. Pre-filled with HubSpot's default sales stages for "
        "the client to edit.",
        "Deal_Stage_Planner",
        lambda: build_template(CONFIG),
    ),
}

project_name_input(label="Client / project name")

# ---- 1. Pre-call templates -------------------------------------------------

st.subheader("1 · Send a pre-call template")
choice = st.selectbox("Template", list(PRECALL_TEMPLATES), key="spl_template_choice")
description, stub, builder = PRECALL_TEMPLATES[choice]
st.caption(description)
client = st.session_state.get("report_project_name", "")
render_export_footer(
    {"xlsx": builder()},
    document_type=f"Pre-call Template — {choice}",
    project_name=client,
    file_stub=f"{client or 'client'}_{stub}".replace(" ", "_"),
)

# ---- 2. Import ---------------------------------------------------------------

st.divider()
st.subheader("2 · Import a filled-out planner")
st.caption(
    "Rows are matched by their label in column A, so inserted, moved or deleted rows are fine. Every stage "
    "column with a name is read; blank and 'Stage name' columns are skipped. Nothing is changed until you "
    "review and click Apply."
)
upload = st.file_uploader("Filled-out Deal Stage Planner (.xlsx)", type=["xlsx"], key="spl_upload")
if upload is not None:
    content = upload.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    if st.session_state.get(DRAFT_HASH_KEY) != digest:
        try:
            parsed = parse_stage_planner(content, CONFIG, source=upload.name)
            st.session_state[DRAFT_KEY] = parsed.to_dict()
            st.session_state[DRAFT_HASH_KEY] = digest
        except StagePlannerParseError as exc:
            st.session_state.pop(DRAFT_KEY, None)
            st.session_state.pop(DRAFT_HASH_KEY, None)
            st.error(str(exc))

draft_data = st.session_state.get(DRAFT_KEY)
if not draft_data:
    record = applied_record()
    if record:
        planner = StagePlanner.from_dict(record["planner"])
        st.info(
            f"A planner with {len(planner.stages)} stages was applied on {record.get('applied_on', 'an earlier date')} "
            f"to: {', '.join(TARGETS[t].split(' — ')[0] for t in record.get('targets', []))}. Upload a new one to replace it."
        )
    st.stop()

draft = StagePlanner.from_dict(draft_data)
st.markdown(f"**Read from `{draft.source}`: {len(draft.stages)} stages**")
if draft.warnings:
    with st.container(border=True):
        st.markdown(f"**⚠ {len(draft.warnings)} thing{'s' if len(draft.warnings) != 1 else ''} to check**")
        st.markdown("\n".join(f"- {w}" for w in draft.warnings))

# ---- Review / edit ---------------------------------------------------------------

st.markdown("##### Review and edit the stages")
st.caption("Edit any cell, add or delete rows, or change Order to re-sequence. Required fields are comma-separated.")
COLUMNS = {
    "order": "Order",
    "name": "Stage",
    "forecast": "Forecast %",
    "entry_criteria": "Entry criteria",
    "exit_criteria": "Exit criteria",
    "actions": "Desired actions",
    "automations": "Automations",
    "fields": "Required fields",
}
table = pd.DataFrame(
    [
        {
            "order": i + 1,
            "name": s.name,
            "forecast": s.forecast,
            "entry_criteria": s.entry_criteria,
            "exit_criteria": s.exit_criteria,
            "actions": s.actions,
            "automations": s.automations,
            "fields": ", ".join(s.fields),
        }
        for i, s in enumerate(draft.stages)
    ],
    columns=list(COLUMNS),
)
edited = st.data_editor(
    table,
    key=f"spl_editor_{st.session_state.get(DRAFT_HASH_KEY, '')[:12]}",
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "order": st.column_config.NumberColumn(COLUMNS["order"], min_value=1, step=1, width="small"),
        "name": st.column_config.TextColumn(COLUMNS["name"], required=True),
        "forecast": st.column_config.NumberColumn(COLUMNS["forecast"], min_value=0, max_value=100, format="%g%%"),
        **{k: st.column_config.TextColumn(v) for k, v in COLUMNS.items() if k not in ("order", "name", "forecast")},
    },
)


def _planner_from_table(df: pd.DataFrame) -> StagePlanner:
    """The reviewed planner: rows with a stage name, sorted by Order (then table position)."""
    rows = [r for r in df.to_dict("records") if str(r.get("name") or "").strip() and str(r.get("name")) != "nan"]
    rows.sort(key=lambda r: (float(r["order"]) if pd.notna(r.get("order")) else 1e9))
    stages = []
    for r in rows:
        def text(key: str) -> str:
            value = r.get(key)
            return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()

        forecast = r.get("forecast")
        stages.append(
            PlannedStage(
                name=text("name"),
                forecast=None if forecast is None or pd.isna(forecast) else float(forecast),
                entry_criteria=text("entry_criteria"),
                exit_criteria=text("exit_criteria"),
                actions=text("actions"),
                automations=text("automations"),
                fields=[f.strip() for f in text("fields").split(",") if f.strip()],
            )
        )
    return StagePlanner(stages=stages, warnings=draft.warnings, source=draft.source)


reviewed = _planner_from_table(edited)

# ---- Preview of what it populates -------------------------------------------------

st.markdown("##### What it will populate")
pipeline = to_pipeline(reviewed, CONFIG)
properties = to_deal_properties(reviewed, CONFIG)
workflows = to_workflows(reviewed, CONFIG)
build_items = to_build_items(reviewed, CONFIG)
section_titles = {s.key: s.title for s in BUILD.sections}

pipe_tab, prop_tab, flow_tab, build_tab, disc_tab = st.tabs(
    [
        f"Pipeline ({len(pipeline.stages)})",
        f"Deal properties ({len(properties)})",
        f"Workflows ({len(workflows)})",
        f"Build-order items ({len(build_items)})",
        "Discovery",
    ]
)
with pipe_tab:
    st.caption(f"{pipeline.name} ({pipeline.object_type}) — replaces the default stages in the Architecture Generator.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Order": s.order,
                    "Stage": s.name,
                    "Probability": "" if s.probability is None else f"{s.probability:.0%}",
                    "Closed": "Won" if s.is_won else ("Lost" if s.is_closed else ""),
                    "Description": s.description,
                }
                for s in pipeline.stages
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
with prop_tab:
    st.caption("Deal properties required at each stage. HubSpot's own properties are mapped, not re-created.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Label": p.label,
                    "Internal name": p.existing or (p.definition.name if p.definition else ""),
                    "Type": "HubSpot default" if p.existing else (p.definition.field_type if p.definition else ""),
                    "Required at": ", ".join(p.stages),
                }
                for p in properties
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
with flow_tab:
    st.caption("One suggested workflow per Automations item, triggered by the deal entering that stage.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Workflow": w.name,
                    "Trigger": w.trigger,
                    "Action": w.action_summary,
                    "Overwrite risk": "YES" if w.overwrite_risk else "",
                }
                for w in workflows
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
with build_tab:
    st.dataframe(
        pd.DataFrame(
            [{"Section": section_titles.get(i.section, i.section), "Item": i.name, "Source": i.source} for i in build_items]
        ),
        hide_index=True,
        use_container_width=True,
    )
with disc_tab:
    st.markdown(f"**{CONFIG.discovery_section} › Sales pipeline stages**")
    st.code(to_discovery_answer(reviewed) or "—", language=None)
    st.markdown(f"**{CONFIG.discovery_section} › Other notes** (added, or replaces an earlier planner block)")
    st.code(to_discovery_notes(reviewed, CONFIG), language=None)

# ---- Apply ------------------------------------------------------------------------

st.markdown("##### Apply")
targets = [t for t, label in TARGETS.items() if st.checkbox(label, value=True, key=f"spl_target_{t}")]

overwrites = []
existing_answer = str(st.session_state.get(ANSWER_KEY) or "").strip()
if TARGET_DISCOVERY in targets and existing_answer and existing_answer != to_discovery_answer(reviewed):
    overwrites.append(f"the Discovery answer “{existing_answer[:80]}{'…' if len(existing_answer) > 80 else ''}”")
record = applied_record()
if record:
    for t in targets:
        if t != TARGET_DISCOVERY and t in (record.get("targets") or []):
            overwrites.append(f"the planner applied on {record.get('applied_on', 'an earlier date')} ({TARGETS[t].split(' — ')[0]})")
if TARGET_ARCHITECTURE in targets and st.session_state.get("blueprint") is not None:
    st.caption("A blueprint is already generated — click Generate on the Architecture Generator again to include the planner.")

confirmed = True
if overwrites:
    st.warning("Applying will replace " + "; ".join(overwrites) + ".")
    confirmed = st.checkbox("Replace what's there", key="spl_confirm_replace")

if st.button(
    "Apply the planner",
    type="primary",
    disabled=not targets or not reviewed.stages or not confirmed,
    key="spl_apply",
):
    if TARGET_DISCOVERY in targets:
        st.session_state[ANSWER_KEY] = to_discovery_answer(reviewed)
        st.session_state[NOTES_KEY] = merge_notes(
            str(st.session_state.get(NOTES_KEY) or ""), to_discovery_notes(reviewed, CONFIG)
        )
    st.session_state[APPLIED_KEY] = {
        "planner": reviewed.to_dict(),
        "targets": targets,
        "applied_on": date.today().isoformat(),
    }
    st.success(
        f"Applied {len(reviewed.stages)} stages to: {', '.join(TARGETS[t].split(' — ')[0] for t in targets)}. "
        "Open those pages to continue — nothing was sent to HubSpot."
    )
if not reviewed.stages:
    st.caption("Add at least one stage to apply.")
