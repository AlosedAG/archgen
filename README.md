# ArchitectureScope

A HubSpot architecture generator, portal auditor, documentation tool, and
project-documentation suite for implementation specialists. Eleven modules,
one Streamlit app, loosely modeled on HubSpot's own solutions-architecture
methodology (Written Requirements Document → ERD → Test Case Document).

The sidebar follows the order a project actually runs in, so a new user
can work top to bottom:

| Sidebar section | Pages |
|---|---|
| **Start here** | Setup & API keys (landing page), User guide |
| **Step 1 · Discover** | Discovery Call Assistant, Requirements Document, Joint Evaluation Plan |
| **Step 2 · Assess current portal** | Portal Auditor, Property Audit, Documentation Generator, Executive Report |
| **Step 3 · Design** | Architecture Generator, Architecture Diagram |
| **Step 4 · Propose** | Proposal & SOW Builder |
| **Step 5 · Deliver & test** | Test Case Document |
| **Library** | Project Library |

`Home.py` is a thin router built on `st.navigation`/`st.Page` — the order
and sections live there, not in the page files under `app_pages/` (whose
file names keep their original module numbers). The router also shows each
page's own section of the in-app guide ([`docs/user_guide.md`](docs/user_guide.md))
under **Guide for this page** in the sidebar; the **User guide** page shows
the whole guide plus the PDF manuals as downloads. When adding a page, add a
`## <page title>` section to the guide (`tests/test_guide.py` enforces it).

1. **Architecture Generator** — turn a project's requirements into a proposed
   HubSpot architecture blueprint. No API access needed.
2. **Portal Auditor** — connect to a live portal (read-only) and check it
   against best practice: duplicate properties, unused properties, missing
   required fields, orphaned records, risky workflows, permission anomalies,
   and naming drift.

   **2B. Property Audit** — connect to a live portal (read-only) and rate
   *every* object and *every* property Keep / Review / Remove candidate,
   based on a sampled fill rate and workflow references. Exports a
   color-matched `.xlsx` workbook (Summary, Flagged for Action, All
   Properties, How to use) and a PDF report capped at 10 pages — both styled
   to match `examples/RPG_property_audit.xlsx` and
   `examples/RPG_HubSpot_Audit_Report.pdf`. Nothing is ever deleted or
   changed in HubSpot; every call is left for a human to make in the
   workbook. See [Module 2B](#module-2b-property-audit) below for the exact
   rating rules and the "Uses" signal's limitations.
3. **Documentation Generator** — connect to a live portal (read-only) and
   generate a documentation pack (data dictionary, workflow inventory,
   association map, pipelines, roles/permissions) as Markdown and .docx.
4. **Executive Report** — turn the snapshot + findings from Modules 2 and 3
   into a plain-language report: what the portal has, how it's structured,
   and what's worth fixing. No API calls of its own — reads what's already
   in the session. One button for a polished client-facing `.docx`, one for
   a full-detail internal-facing `.docx`.
5. **Architecture Diagram** — turns the blueprint and/or portal snapshot
   (with audit findings highlighted on it) into an editable entity/
   association diagram. Edit the underlying object/connection tables
   in-app, then export to diagrams.net for full drag-and-drop editing.
6. **Requirements Document** — a Written Requirements Document (WRD):
   purpose/goals, numbered customer requirements, project-specific
   terminology, known risks, a draft project plan, open questions, and
   appendix links.
7. **Joint Evaluation Plan** — team roster, milestones (what/when/who),
   technical/business needs, and open questions for an evaluation.
8. **Test Case Document** — one row per QA/UAT test case, with steps,
   expected/actual results, and feedback. Can optionally pull its starting
   rows from Module 6's Customer Requirements (a one-off prefill, not a
   live link).
9. **Project Library** — every module's "Save to Project Library" button
   writes here: a local, folder-per-project, folder-per-document-type
   archive of everything generated, each file tagged with the date it was
   generated.
10. **Proposal & SOW Builder** — turns the Requirements Document and Joint
    Evaluation Plan into a SonaMation-branded proposal and/or Statement of
    Work PDF: Technical, Management, and Cost volumes, plus a "Scope at a
    Glance" page listing what is included, excluded, available as an
    add-on, or the client's responsibility.
11. **Discovery Call Assistant** — filled in live during a discovery call.
    Shorthand notes under Goals / Data / Processes / Solutions Design become
    (a) a structured business-analysis document — executive summary, current
    state, requirements, preliminary scope signals for the SOW, and a
    specific follow-up list for every question left blank — and (b) a
    plain-language explainer of the HubSpot hubs the client needs. Drafted
    by Claude (`core/discovery.py` holds the system prompt and question
    bank); exports `.docx`, `.pdf`, and `.md`. The only module that needs an
    Anthropic API key, and the only one that sends anything outside your
    machine besides HubSpot reads — notes go to Anthropic only when a
    Generate button is clicked.

Modules 6-8 are pure documentation/tracking — no HubSpot API calls, no
generated logic, no approval gating, and no dependency on any other
module's output (a soft, overridable default only, where one exists).
Every module's output downloads as `.docx`, `.xlsx`, and `.csv` — all
directly editable afterward in Word/Excel or Google Docs/Sheets — plus a
`.pdf` for a portable, read-only copy.

**This tool is read-only against HubSpot.** Every HubSpot API call it makes is a GET, or a
POST against one of HubSpot's own "batch read" query endpoints (which don't
mutate data — that's just how HubSpot designed those endpoints). Nothing in
this codebase creates, updates, or deletes anything in a connected portal.

## Setup

Requires Python 3.11+.

```bash
pip install -r requirements.txt
streamlit run Home.py
```

The app opens on **Setup & API keys**, with every page listed in process order in the sidebar.

## Authentication

The **Setup & API keys** page (first in the sidebar, and the landing page)
is where both keys go:

- **HubSpot private app token** — Portal Auditor, Property Audit,
  Documentation Generator. See [private apps](https://developers.hubspot.com/docs/api/private-apps)
  and the scope table below.
- **Anthropic API key** — Discovery Call Assistant only. Create one at
  [console.anthropic.com](https://console.anthropic.com). The model defaults
  to `claude-opus-5-5`; override with `ANTHROPIC_MODEL`.

Provide each one of two ways:

- **Environment / `.env`** (recommended for regular use): copy `.env.example`
  to `.env` and fill in `HUBSPOT_TOKEN` / `ANTHROPIC_API_KEY`; the app loads
  `.env` at startup.
- **In the UI**: paste into the password-masked fields on the Setup page
  (the portal pages also offer the HubSpot field inline if no token is set).
  Held only in `st.session_state` for that session — never written to disk,
  never logged, never sent anywhere but HubSpot's / Anthropic's API.

`.env` and `.streamlit/secrets.toml` are already in `.gitignore` — don't
commit real tokens.

### Required private-app scopes

Create the private app with these scopes. Exact scope names occasionally
shift in HubSpot's scope picker — verify against your portal's private app
creation screen if a pull fails with a scope error (the app surfaces the
HTTP 403 and tells you a scope is likely missing, rather than crashing).

| Feature | Scopes |
|---|---|
| Standard object schemas & properties | `crm.schemas.contacts.read`, `crm.schemas.companies.read`, `crm.schemas.deals.read`, `tickets` |
| Custom object schemas & properties | `crm.schemas.custom.read` |
| Record sampling (unused/required property checks, orphan checks) | `crm.objects.contacts.read`, `crm.objects.companies.read`, `crm.objects.deals.read`, `crm.objects.tickets.read`, `crm.objects.custom.read` |
| Pipelines | Covered by the object read scopes above (deals/tickets/custom pipelines ride on their parent object's read scope) |
| Workflows (legacy Automation API) | `automation` |
| Owners | `crm.objects.owners.read` |
| Teams | `settings.users.teams.read` |

If you only want to try the Documentation Generator on a subset of objects,
grant a subset of the scopes above — the app will report what it couldn't
pull (as a warning, not a crash) and generate documentation from whatever it
could fetch.

## Module 1: Architecture Generator

Fill in the form (object model needs, pipelines, regions/currencies,
integrations, estimated record volumes, hubs in scope) and click
**Generate blueprint**. Click **Load sample project** first to see it work
end-to-end with zero setup — it loads `sample_inputs/example_project.json`,
a fictional gym/wellness studio implementation.

The blueprint includes recommended custom objects, a full property data
dictionary, an association model, pipeline/stage definitions, a naming
convention summary, a base-currency recommendation, and a suggested
workflow list — each workflow flagged `Overwrite Risk: Yes/No` based on
whether it sets a property unconditionally. Export as Markdown or JSON.

All the logic is table-driven from [`rules/rules.yaml`](rules/rules.yaml),
loaded by [`rules/engine.py`](rules/engine.py) — edit the YAML to tune
naming conventions, pipeline templates, integration heuristics, or the
overwrite-risk keyword list without touching code.

## Module 2: Portal Auditor

Enter a token, click **Pull from portal**, then **Run audit**. Checks run:

- Duplicate property definitions (same label, different internal name) and
  near-duplicate picklist options (via string similarity)
- Unused properties (no value set in a sample of records)
- Required properties (per the Module 1 baseline rules) missing on a sample
  of records
- Orphaned/unassociated custom-object records (sampled)
- Workflows with re-enrollment enabled that also set a property with no
  visible conditional branch
- Permission/team anomalies (owners with no team, teams with no members)
- Naming-convention drift — checked against the exact same rules the
  Architecture Generator uses

Every record-level check samples (default 100 records per object,
configurable in `rules.yaml`'s `audit_thresholds.record_sample_size`) and
says so directly in the finding. Findings are filterable by severity and
area, and export to CSV or Markdown.

**Known scope limitations** (documented here rather than silently assumed):
workflow inspection uses the legacy v3 Automation API, so custom-coded
workflows/newer "flows" aren't included. The orphan check only follows each
custom object's *first* declared association. The association map (in
Module 3, reused conceptually here) only reflects associations declared on
custom object schemas — HubSpot's API doesn't expose default
standard-to-standard association definitions the same way.

## Module 2B: Property Audit

Enter a token, click **Pull from portal**, then **Run property audit**.
Rates *every* property on *every* object — standard and custom — Keep /
Review / Remove candidate, then exports a workbook and a PDF report styled
to match `examples/RPG_property_audit.xlsx` and
`examples/RPG_HubSpot_Audit_Report.pdf` (same header/accent colors, same
Keep/Review/Remove badge colors, same four-tab workbook shape) — so a
reviewer familiar with those reference files gets the same read on this
tool's output. Nothing is deleted, archived, or changed in HubSpot; every
call is left in the workbook for a human to check first.

Two signals decide a **custom** property's rating (native/HubSpot-defined
properties are always Keep, matching the reference workbook's own rule):

- **Fill %** — share of a sample of records (default 100, same
  `record_sample_size` setting Module 2 uses) that have a value set.
- **Uses** — number of this portal's workflows whose actions reference the
  property by internal name.

| Rating | Rule |
|---|---|
| Remove candidate | Custom, under 5% filled, referenced by no workflow. |
| Review | Custom, and either referenced by a workflow but under 25% filled, or 5%+ filled but referenced by no workflow. |
| Keep | Native property (always), or custom with 25%+ fill and at least one workflow reference. |

These thresholds were reverse-engineered from the rating boundaries in
`examples/RPG_property_audit.xlsx` so this tool's calls read the way a
reviewer of that workbook would expect — see
[`core/property_audit.py`](core/property_audit.py)'s `_rate_property` for
the exact logic and the tests that pin each boundary.

**Known scope limitation:** this tool is read-only and only pulls
workflows — it does not read forms, lists, reports, or dashboards. "Uses"
therefore undercounts real usage whenever a property is only referenced
from one of those; every export (workbook, PDF, and the in-app page) says
so directly rather than implying a complete usage picture.

The workbook has four tabs — **Summary** (per-object counts and a cleanup
score, worst-first), **All Properties** (every property, one row each,
with blank Notes/Tag columns to fill in during review), **Flagged for
Action** (just the Remove/Review rows — the actual cleanup worklist), and
**How to use**. The PDF report is capped at 10 pages: if a portal has more
objects than fit, the per-object breakdown section is trimmed first (the
Summary/Key findings/Methodology pages always render in full) rather than
letting the report grow unbounded.

## Module 3: Documentation Generator

Enter a token, click **Pull from portal**. Generates: a data dictionary
(every object → properties, types, options), a workflow inventory, an
association map, a pipeline/stage list, and a roles/permissions summary
(teams + owners). Preview each section in the UI, then export as Markdown
or as a styled `.docx` (title page, heading-styled sections, tables) via
[`python-docx`](https://python-docx.readthedocs.io/).

The `.docx` section order (Data Dictionary → Workflow Inventory →
Association Map → Pipelines & Stages → Roles & Permissions) is a sensible
default — reorder the headings in `core/docgen.py`'s `snapshot_to_docx` if
you want it to match a specific existing tracker template.

## Module 4: Executive Report

Open the page after pulling a snapshot (Module 3) and, ideally, running an
audit (Module 2) — this module reads both from `st.session_state` and makes
no HubSpot API calls itself. Optionally type a client/project name to
personalize the title, then preview the report on-screen: an overall health
rating (`Excellent`/`Good`/`Fair`/`Needs Attention`, based on the count of
High/Medium findings only — Low-priority items are cosmetic and don't move
the rating), an object-model table with plain-language "connects to"
summaries, pipeline/automation/team stats, and findings grouped by area and
severity with a short explanation of *why each category matters*, not just
what was found.

Two downloads, matching two different audiences:

- **Client report (`.docx`)** — polished and plain-language. Findings are
  capped at 3 representative examples per category ("...and N more like
  this.") so it stays readable; safe to hand to a client as-is.
- **Internal report (`.docx`)** — full technical detail: every finding (no
  capping, laid out in tables), raw property-group breakdowns, association
  type IDs, an area × severity summary table. Meant for internal use/context
  (tickets, handoff notes), not client distribution.

Both exports are built from the same computed `ReportContext`
(`core/report.py`), so the two documents' numbers never disagree with each
other. If no audit has been run yet, the report still describes the
portal's structure and says so plainly instead of claiming a false "all
clear."

## Module 5: Architecture Diagram

Pick a source (a live snapshot, if pulled, is preferred over the blueprint,
since it reflects the real portal) and the objects/associations load into
two editable tables — the generator and the audit are both heuristic, so
this is where you fix anything they got wrong before rendering: rename an
object, drop a spurious connection, correct a cardinality, mute a finding
that doesn't apply. The diagram re-renders live from the edited tables,
with a colored border on any object carrying an audit finding (red/orange/
yellow by severity). "Reset to generated data" discards edits and rebuilds
from the current source.

Exports: a diagrams.net (`.drawio`) file — opens in
[app.diagrams.net](https://app.diagrams.net) (free, no login) for full
drag-and-drop editing — plus Graphviz `.gv` source and the edited table
data as `.json` / `.xlsx` / `.csv`.

On a live portal, most objects also associate to HubSpot's generic
engagement types (Task, Note, Email, Call, Meeting, ...) — these are on
every portal, aren't part of the client's own data model, and can easily
outnumber the objects that actually matter, so they're **excluded by
default** (a checkbox brings them back in, styled as a distinct dashed
"Activity" node kind). Multiple association definitions between the same
two objects are merged into one edge automatically. A **"Focus diagram
on"** multiselect narrows the diagram/charts/exports to a chosen subset of
objects without touching the underlying tables, and a **"Show connection
labels"** checkbox turns off edge-label text for a still-busy graph.

## Modules 6-8: Requirements Document, Joint Evaluation Plan, Test Case Document

Three self-contained note-taking modules, structured the same way as
HubSpot's own templates for each document. Every table is an
`st.data_editor` with dynamic rows — add, delete, or edit anything — and
every one exports as `.docx`, `.xlsx`, `.csv`, and `.pdf` via the shared
`core/exporters.py` (a `Section = (title, rows)` list feeds all four
formats, so they can never drift out of sync with each other).

- **Requirements Document** (`app_pages/6_Requirements_Document.py`) — Project
  Overview, Customer Requirements, Project Definitions, Known Challenges or
  Risks, Project Plan, Open Questions, Appendix and Resources.
- **Joint Evaluation Plan** (`app_pages/7_Joint_Evaluation_Plan.py`) — solutions
  partner contact, milestones (target date/status/owner/outcome), team
  roster, technical needs, business needs, and questions.
- **Test Case Document** (`app_pages/8_Test_Case_Document.py`) — one row per
  test case (requirement, steps, expected/actual result, round, feedback).
  If a Requirements Document already exists in the session, a button offers
  to load its Customer Requirements in as starting rows — a one-off
  prefill (via a plain session-state snapshot, not a live binding), so
  editing the WRD afterward has no effect on rows already loaded here.

None of these three modules require another module's output to run, and
none of them gate on any kind of approval/sign-off — they're documentation
and tracking tools, not a workflow engine.

## Module 10: Proposal & SOW Builder

`app_pages/10_Proposal_SOW_Builder.py` (UI), `core/proposal.py` (data model,
SonaMation defaults, pricing/scope/coverage logic, WRD/JEP import, JSON
round-trip), `core/proposal_pdf.py` (branded PDF). Based on the Statement of
Work short form: parties and notice contacts, effective/expiration dates,
description of services, deliverables and milestone fee schedule, optional
additional-services menu, payment, and expenses.

Tabs follow the three areas a proposal must cover:

- **Technical** — understanding of the problem, objectives, numbered
  requirements (R-01...), proposed solution, methodology, tools & platforms,
  techniques & procedures, glossary.
- **Scope** — one table where every item is *In Scope*, *Out of Scope*,
  *Optional Add-on*, or *Client Responsibility*, with a quantity limit,
  acceptance criteria, and the requirement IDs it satisfies. Preset
  libraries of common deliverables and add-on services, a live preview of
  the "Scope at a Glance" page, and a requirements-coverage check that
  flags anything not covered by an In Scope item.
- **Management** — team & roles, governance cadence, schedule, risks,
  targeted KPIs (primary/secondary), acceptance process.
- **Cost** — milestone schedule with fees, add-on menu ("Add to Total" for
  chosen add-ons; recurring fees reported separately from one-time),
  rate card for change requests, discount, payment/expense terms.
- **Review & Generate** — optional-section toggles, pre-send warnings,
  PDF download, and `.json` downloads (a full editable copy, or a reusable
  template with deal-specific content stripped) that load back in from
  the Setup tab.

Standard text (company overview, methodology, change-control, acceptance,
payment, expenses, confidentiality) is pre-filled and editable. Imports from
the WRD/JEP are one-off merges that fill blanks and append rows; they need
that page to have been opened in the same session.

## Module 9: Project Library

Every module above has a **Save to Project Library** button next to its
downloads. It writes every export format for that document to
`project_library/<project name>/<document type>/<document type>_<timestamp>.<ext>`
on local disk (configurable via the `PROJECT_LIBRARY_DIR` environment
variable; git-ignored by default). Module 9 (`app_pages/9_Project_Library.py`)
browses that archive — pick a project, see everything saved for it grouped
by document type with the date each file was generated, re-download any
file, or delete one. Purely local files, no database, consistent with the
rest of the app never touching anything but HubSpot (read-only) and the
local filesystem.

## Caching

Modules 2 and 3 cache the pulled portal snapshot in
`st.session_state["portal_snapshot"]` for the session — switching pages or
re-rendering doesn't re-hit the API. Click **Refresh portal data** /
**Refresh from portal** to force a new pull. Module 4 reads that same
session state (plus `st.session_state["audit_findings"]` from Module 2, if
present) rather than caching anything of its own.

## Testing

```bash
pytest
```

All tests run with no network access and no live portal — Module 1's tests
exercise the rules engine and blueprint generation directly; Module 2 and
3's tests mock `HubSpotClient`'s pull methods with canned data engineered
to trip every check at least once (plus a "clean" fixture with zero
findings, as a regression guard); Module 4's tests build `PortalSnapshot`/
`Finding` fixtures directly (it has no HubSpot client of its own) and assert
on both the computed stats and the two export formats. Module 5's tests
cover both builders (blueprint- and snapshot-sourced), the DOT/`.drawio`
renderers, and dangling-edge handling. `core/exporters.py` and
`core/project_store.py` (shared by Modules 5-9) are tested directly —
including a `.docx`/`.xlsx`/`.pdf` round trip and the Unicode punctuation
this app's own copy uses throughout (dashes, arrows, middots) surviving
fpdf2's Latin-1-only core font. Module 2B's tests
(`tests/test_property_audit.py`) pin each rating-boundary case reverse-
engineered from `examples/RPG_property_audit.xlsx`, assert the exported
workbook's sheet/column shape, and check the PDF report stays within the
10-page cap for a large synthetic portal. `tests/test_pages_smoke.py`
drives the actual Streamlit pages via `streamlit.testing.v1.AppTest`,
including the WRD-to-Test-Case-Document prefill, a full "Save to Project
Library" click generating all four formats, and — via `Home.py`, the real
entrypoint — a check that every page in every sidebar section still
resolves and renders through `st.navigation`.

## Project structure

```
architecturescope/
├── Home.py                          # Streamlit entry point — st.navigation router, sidebar sections
├── app_pages/
│   ├── 0_Home.py
│   ├── 1_Architecture_Generator.py
│   ├── 2_Portal_Auditor.py
│   ├── 2b_Property_Audit.py
│   ├── 3_Documentation_Generator.py
│   ├── 4_Executive_Report.py
│   ├── 5_Architecture_Diagram.py
│   ├── 6_Requirements_Document.py
│   ├── 7_Joint_Evaluation_Plan.py
│   ├── 8_Test_Case_Document.py
│   ├── 9_Project_Library.py
│   └── 10_Proposal_SOW_Builder.py
├── core/
│   ├── models.py           # shared dataclasses for all modules
│   ├── hubspot_client.py   # read-only API client: pagination, 429 backoff, scope errors
│   ├── blueprint.py        # Module 1 generation + Markdown/JSON export
│   ├── docgen.py           # Module 3 portal pull + Markdown/docx export
│   ├── audit.py            # Module 2 checks + CSV/Markdown export
│   ├── property_audit.py   # Module 2B: per-property rating + .xlsx/PDF export matching examples/
│   ├── report.py           # Module 4: snapshot+findings -> plain-language report, client + internal .docx export
│   ├── diagram.py          # Module 5: node/edge model + DOT/.drawio/.json rendering
│   ├── exporters.py        # Section -> .docx/.xlsx/.csv/.pdf, shared by Modules 5-9
│   ├── doc_export_ui.py    # Streamlit download-row + "Save to Project Library" button, shared by all modules
│   ├── proposal.py         # Module 10: proposal model, defaults, scope/pricing logic, WRD/JEP import
│   ├── proposal_pdf.py     # Module 10: SonaMation-branded proposal/SOW PDF
│   ├── theme.py             # brand CSS + the audit .xlsx/PDF color palette (matches examples/)
│   └── project_store.py    # Module 9's filesystem-backed save/list/delete
├── rules/
│   ├── rules.yaml         # editable best-practice rules
│   └── engine.py          # loads rules.yaml, exposes naming/risk checks
├── examples/                # reference audit workbook + PDF report this app's palette/shape is matched to
├── sample_inputs/
│   └── example_project.json
├── project_library/        # generated at runtime, git-ignored — Module 9's saved output
└── tests/
```

## Known limitations (MVP scope)

- Workflow inspection uses HubSpot's legacy v3 Automation API; newer
  "flows"/custom-coded actions aren't parsed.
- The association map only reflects custom-object schema associations, not
  default standard-object associations (not exposed the same way by the API).
- Object-model and integration heuristics in `rules.yaml` are intentionally
  simple pattern-matches, not a general NLP/ML model — extend the YAML for
  your own recurring project patterns.
- Module 2B's "Uses" signal only counts workflow-action references (this app
  doesn't pull forms, lists, reports, or dashboards), so it can undercount a
  property that's only referenced from one of those — treat "Remove
  candidate" as a starting worklist to verify, not an automatic delete list.
