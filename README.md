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
    plain-language explainer of the HubSpot hubs the client needs. Answers
    are dropdowns / multiselects with an "Other (specify)" fallback, a
    shorthand notes line, and a "Flag for follow-up" checkbox per question;
    the questions and options live in
    [`packages/domain/src/archscope_domain/config/discovery_options.yaml`](packages/domain/src/archscope_domain/config/discovery_options.yaml) (see
    [Discovery question bank](#discovery-question-bank)). Answers like EU / UK
    contacts or multiple locations reveal follow-up questions and add
    required tasks to a checklist, driven by `discovery_rules.yaml` (see
    [Discovery "gotcha" rules](#discovery-gotcha-rules)), and those tasks plus
    the scope captured export as a required-tasks checklist (see
    [Discovery required-tasks checklist](#discovery-required-tasks-checklist)) and
    as a categorized build order with reusable-template items tagged (see
    [Discovery build order](#discovery-build-order)). Drafted by Claude
    (`packages/domain/src/archscope_domain/discovery.py` holds the system prompt); exports `.docx`, `.pdf`, and `.md`. The only module that needs an
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

Requires Python 3.12+. (Developing on the platform rebuild? See
[Platform (rebuild)](#platform-rebuild).)

```bash
pip install -r requirements.txt
streamlit run Home.py
```

The app opens on **Setup & API keys**, with every page listed in process order in the sidebar.

### Sign-in

Every page sits behind a sign-in screen (`core/auth.py`): **Sign in with
Google** and/or **username + password**, configured in
`.streamlit/secrets.toml` (locally) or the app's **Secrets** box on
Streamlit Community Cloud. See `.streamlit/secrets.toml.example`:

- `[auth]` enables Google sign-in (Streamlit's built-in OIDC). Only emails in
  `[access] allowed_emails` or domains in `allowed_domains` get in.
- `[passwords]` enables username + password. Generate a password hash with
  `python -m core.auth`.

With neither configured the app refuses to open. For local development
without sign-in, set `AUTH_DISABLED=1` in `.env`.

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

All the logic is table-driven from [`packages/domain/src/archscope_domain/config/rules.yaml`](packages/domain/src/archscope_domain/config/rules.yaml),
loaded by [`packages/domain/src/archscope_domain/rules.py`](packages/domain/src/archscope_domain/rules.py) — edit the YAML to tune
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
[`packages/domain/src/archscope_domain/property_audit.py`](packages/domain/src/archscope_domain/property_audit.py)'s `_rate_property` for
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
default — reorder the headings in `packages/domain/src/archscope_domain/docgen.py`'s `snapshot_to_docx` if
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
(`packages/domain/src/archscope_domain/report.py`), so the two documents' numbers never disagree with each
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
`packages/domain/src/archscope_domain/exporters.py` (a `Section = (title, rows)` list feeds all four
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

`app_pages/10_Proposal_SOW_Builder.py` (UI), `packages/domain/src/archscope_domain/proposal.py` (data model,
SonaMation defaults, pricing/scope/coverage logic, WRD/JEP import, JSON
round-trip), `packages/domain/src/archscope_domain/proposal_pdf.py` (branded PDF). Based on the Statement of
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

## Discovery question bank

[`packages/domain/src/archscope_domain/config/discovery_options.yaml`](packages/domain/src/archscope_domain/config/discovery_options.yaml) is the
single source of truth for every question the Discovery Call Assistant
asks: its section (Goals, Data, Processes, Solutions Design), its label,
its input type, and its standard answer options. Edit it to standardize
options across the team, reword or reorder questions, or add new ones —
no code changes needed.

- **Input types:** `multiselect` (any number of options), `select`
  (one, as a dropdown), `radio` (one, shown inline — best for five
  options or fewer), or `text` (free text, no options).
- **"Other (specify)"** is appended to every option list automatically
  (rename it with the top-level `other_option:` key), along with a free-text
  box for it, a notes line, and a follow-up flag. Don't list those in the YAML.
- **Section intros:** the optional top-level `section_descriptions:` maps a
  section name to the one-line intro shown under its heading (both apps).
- **Ids** are snake_case and unique across all sections. Saved notes
  refer to questions by id, so rename the `label`, not the `id`, when
  rewording.
- **Editing safely:** changes are picked up on the next page refresh. If
  the file has a mistake, the page lists each bad entry instead of
  showing the form; `pytest tests/test_discovery_config.py` checks the
  same thing. Removing an option doesn't lose answers that used it — they
  move into that question's "Other" text.

The file is loaded and validated by
[`packages/domain/src/archscope_domain/discovery_config.py`](packages/domain/src/archscope_domain/discovery_config.py). Answers are sent
to the AI as one readable line per question (selections, "Other" text,
then notes), and flagged questions are listed with the section's edge
cases, so the business-analysis prompt itself is unchanged.

### Discovery "gotcha" rules

[`packages/domain/src/archscope_domain/config/discovery_rules.yaml`](packages/domain/src/archscope_domain/config/discovery_rules.yaml)
holds the conditional follow-ups: when a specific answer is picked, the
page reveals extra questions inline under it (marked **↳ Follow-up**)
and adds required tasks to a **Required tasks** checklist above the
sections. Each rule is

```yaml
- trigger: {question_id: data_regions, value: "EU / UK"}   # value: one option, or a list (any of)
  reveals: [gdpr_lawful_basis, data_residency]              # ids under follow_ups:
  flags: [gdpr_consent_setup, gdpr_data_residency]          # ids under tasks:
```

with the follow-up questions (same format as the question bank) and the
tasks (`label`, optional `detail`) defined in the same file. Shipped
rules cover EU / UK contacts or GDPR (lawful basis, consent capture,
data residency) and more than one location (per-location ownership and
routing). A trigger can point at a follow-up, so rules chain — e.g.
multi-region → "What differs between regions?" → multiple currencies →
a multi-currency task.

Every reference is checked against the question bank on load: an
unknown id, or a trigger `value` that isn't exactly one of the
question's options, is listed on the page instead of the rule silently
never firing (`pytest packages/domain/tests/test_discovery_rules.py`
checks the same). Revealed follow-ups are sent to the AI right after the
question that revealed them — blank ones become gaps — and required
tasks are listed with the section's edge cases. Loaded by
[`packages/domain/src/archscope_domain/discovery_rules.py`](packages/domain/src/archscope_domain/discovery_rules.py).

### Discovery required-tasks checklist

The Discovery Call Assistant's **3 · Required-tasks checklist** tab turns
the call into a checklist with two parts: **Required tasks** (everything
the gotcha rules flagged) and **Scope items** (one row per option picked
on selected questions — each integration, must-have feature, automation,
custom data element). Every row has the task, why it's required (the
answer that triggered it), and an empty **Status / Notes** column. It
exports as `.docx`, `.xlsx`, `.csv`, and `.pdf`, and **Save to Project
Library** files it under the client as "Discovery Checklist".

Which questions produce scope items is set in
[`packages/domain/src/archscope_domain/config/discovery_checklist.yaml`](packages/domain/src/archscope_domain/config/discovery_checklist.yaml):

```yaml
scope_items:
  - question_id: integrations      # a choice question or follow-up id
    name: "Integration"            # optional item prefix -> "Integration: Salesforce"
  - question_id: custom_data
    name: "Custom data"
    exclude: [None identified]     # optional options that aren't scope
```

A picked "Other (specify)" becomes an item with the typed text. Like the
other discovery files it's validated on load (unknown ids, text
questions, and `exclude` options that don't match exactly are listed on
the page). Loaded by
[`packages/domain/src/archscope_domain/discovery_checklist.py`](packages/domain/src/archscope_domain/discovery_checklist.py).

### Deal Stage Planner (pre-call template + import)

The **Deal Stage Planner** page (Step 1) exports SonaMation's HubSpot Deal
Stage Planner as a pre-call template (.xlsx: Instructions + Planner tabs,
one column per stage) and imports a client's filled-out copy. The import is
parsed (`packages/domain/src/archscope_domain/stage_planner.py`), shown for
review and editing, and only applied on request — with a confirmation
before replacing earlier work — to:

- **Discovery** — Processes › "Sales pipeline stages" (stages in order with
  win %) and a `[Deal Stage Planner]` block in the Processes notes;
- **Architecture Generator** — the deal pipeline (stage order, Forecast % as
  stage probability, Entry / Exit criteria as stage descriptions), every
  "Field to Fill Out" as a deal property tagged with the stage(s) that
  require it, and one suggested workflow per Automations item;
- **Build order** — the pipeline, each new deal property, each automation
  and desired action, and the deal record page.

Parsing is defensive: rows are matched by their column-A label (with
aliases), not position; any number of stage columns and field rows;
blank, "Stage name" and "N/A" cells skipped; forecasts as 40, "40%" or 0.4;
everything skipped or guessed at is listed as a warning. Read-only against
HubSpot — nothing deploys. `POST /api/v1/stage-planner/import` and
`GET /api/v1/stage-planner/template` expose the same for the web app.

Everything about the format is in
[`packages/domain/src/archscope_domain/config/stage_planner.yaml`](packages/domain/src/archscope_domain/config/stage_planner.yaml):
`rows` (each row's `key`, template `label`, and `aliases` accepted on
import), `fields_section` (header label / aliases, `Field {n}` row label),
`placeholders` and `empty_markers` (cells read as blank), `item_separators`
(how Actions / Automations split into items), `template` (title,
instructions, the example stages written to the blank template), and
`mapping` (Closed Won / Lost detection, the Discovery question, property
types by keyword, labels mapped to HubSpot's own deal properties, and the
build-order item names). Edit it to change the template or what an import
produces — no code changes; it's validated on load.

### Discovery build order

The **4 · Build order** tab turns the confirmed scope into "[Client] —
[Project Type] — Build Order" for the implementation team: checkable
items grouped under configurable sections (shipped: Assets to be
created, Segments / Lists, Properties, Pipelines, Record-page updates),
each with its source (the required task, scope item, or answer it came
from) and a status. Items deployable from a reusable template (e.g. the
GDPR asset bundle) are tagged **♻ Template** and listed first in their
section; the rest are marked **Build from scratch**. It exports as
`.docx`, `.xlsx`, `.csv`, `.pdf`, and `.json`, and saves to the Project
Library under the client as "Discovery Build Order".

The `.json` is the build order as structured data
(`BuildOrder.to_dict()`, schema `archscope.build_order/v1`: sections →
items with id, name, sources, template, status, done), so it can later
be pushed to a task tool such as ClickUp. No such integration exists —
nothing is sent anywhere, and HubSpot stays read-only.

Everything is set in
[`packages/domain/src/archscope_domain/config/discovery_build_order.yaml`](packages/domain/src/archscope_domain/config/discovery_build_order.yaml):
`project_types` (for the title), `statuses` and `done_status`,
`sections` (`id` + header `title` — rename or reorder freely),
`templates` (`id: label`), and `items`:

```yaml
- id: gdpr_form_consent            # stable id (tick-marks and JSON use it)
  section: assets
  name: "Consent checkboxes on every form"
  template: gdpr_bundle            # optional: tag as a template item
  task: gdpr_consent_setup         # trigger: a discovery_rules.yaml task...
- id: integration_setup
  section: assets
  name: "Integration: {option}"    # ...or one item per scope item picked
  scope: integrations              #    (a discovery_checklist.yaml question)
- id: sales_pipeline
  section: pipelines
  name: "Sales deal pipeline and stages"
  answer: {question_id: priority_features, value: Deal pipelines}   # ...or an answer
```

Items with the same section and name merge into one listing every
source. The file is validated on load against the other discovery
files (unknown sections, templates, tasks, scope questions, or options
are listed on the page). Loaded by
[`packages/domain/src/archscope_domain/discovery_build_order.py`](packages/domain/src/archscope_domain/discovery_build_order.py).

## In-app feedback

Every page has an orange **Feedback** button in the bottom-right corner.
It opens a small chat where users pick **Bug / Idea / Question**, describe
what happened, attach up to 5 screenshots or PDFs (the + button), and press
send. The app emails it to the owner with the page name, time and the
signed-in user's address (set as Reply-To, so answering is one click).

Configure the sending mailbox in the app's secrets — the `[feedback]`
section of [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)
(on Streamlit Community Cloud: **App settings → Secrets**). For a Google
Workspace account, use an **App Password** (Google Account → Security →
2-Step Verification → App passwords), not the normal password. Without
this section the button still opens but tells users to email instead.

Code: `core/feedback.py` (email building/sending, unit-tested) and
`core/feedback_ui.py` (the floating chat widget, added to every page by
`Home.py`).

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
renderers, and dangling-edge handling. `packages/domain/src/archscope_domain/exporters.py` and
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

The codebase is mid-migration from a single Streamlit app to a decoupled
platform (FastAPI + Next.js) — see [Platform (rebuild)](#platform-rebuild).
Business logic lives in one framework-free package that both the legacy
Streamlit app and the new API import, so they can't drift apart.

```
architecturescope/
├── packages/
│   ├── domain/                       archscope_domain — pure business logic, no I/O, no frameworks
│   │   ├── src/archscope_domain/
│   │   │   ├── models.py             shared dataclasses (blueprint, portal snapshot, findings)
│   │   │   ├── ports.py              PortalReader: the read-only interface the domain reads portals through
│   │   │   ├── rules.py              RulesEngine over config/rules.yaml
│   │   │   ├── blueprint.py          Module 1 generation + Markdown/JSON
│   │   │   ├── audit.py              Module 2 checks + CSV/Markdown
│   │   │   ├── property_audit.py     Module 2B rating + .xlsx/PDF matching examples/
│   │   │   ├── docgen.py             Module 3 portal pull + Markdown/.docx
│   │   │   ├── report.py             Module 4 report figures + client/internal .docx
│   │   │   ├── diagram.py            Module 5 node/edge model + DOT/.drawio/PNG
│   │   │   ├── proposal.py, proposal_pdf.py   Module 10 model, pricing/scope logic, branded PDF
│   │   │   ├── discovery*.py              Module 11 payloads, system prompt, question bank, follow-up rules, checklist, build order
│   │   │   ├── stage_planner.py      Deal Stage Planner template export + import / mapping
│   │   │   ├── exporters.py          sections/Markdown -> .docx/.xlsx/.csv/.pdf
│   │   │   ├── branding.py           brand palette shared by every renderer
│   │   │   └── config/               rules.yaml, discovery_options/_rules/_checklist/_build_order.yaml, stage_planner.yaml (editable, no code changes)
│   │   └── tests/                    unit tests + golden/ parity fixtures
│   └── integrations/                 archscope_integrations — HubSpotClient (read-only PortalReader adapter)
├── apps/
│   ├── web/                          Next.js front end (Discovery so far) — see "Web app"
│   │   ├── src/app/, src/components/ pages, shell, animated discovery UI (Framer Motion)
│   │   └── src/lib/                  typed API client (api-types.ts generated from openapi.json)
│   └── api/                          archscope_api — FastAPI service
│       ├── src/archscope_api/
│       │   ├── main.py               app factory, middleware, routers
│       │   ├── routers/              HTTP only (v1/: architecture, portal, proposals, discovery, exports)
│       │   ├── services/             use cases over the domain (never see HTTP schemas)
│       │   ├── schemas/              Pydantic v2 public contract + domain mappers
│       │   └── problems.py           RFC 9457 problem+json errors
│       ├── openapi.json              committed API contract (CI fails if stale)
│       └── tests/
├── Home.py, app_pages/, core/        legacy Streamlit app (UI only; retired module by module)
├── tests/                            Streamlit smoke tests
├── sample_inputs/example_project.json
├── examples/                         reference audit workbook + PDF the exports are matched to
├── pyproject.toml, uv.lock           uv workspace, tooling config, architecture contracts
└── .github/workflows/          ci-python.yml, ci-web.yml
```

## Platform (rebuild)

Target: Next.js (TypeScript) web app → FastAPI → PostgreSQL, with the
domain package at the core; the Streamlit app is being retired page by
page. Phase 1 (done): domain extraction and the stateless API. Phase 2
(done): accounts and sign-in, workspaces, client projects with saved
per-module state, the project library, and encrypted stored credentials.
Phase 3 (in progress): the web app — Discovery, Projects, Project
Library and Setup are live; the remaining pages are being ported in
workflow order (Stage Planner, Requirements Document, Joint Evaluation
Plan → Portal Auditor, Property Audit, Documentation, Executive Report →
Architecture Generator and Diagram → Proposal & SOW → Test Cases → User
guide). Google sign-in is next on the auth side.

**Local development** (Python 3.12+, [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-packages                          # workspace + dev tools, from uv.lock
uv run python -m archscope_api.cli migrate      # create / upgrade the database (var/archscope.db)
uv run python -m archscope_api.cli create-user --email you@company.com --name "You" --workspace SonaMation --role owner
uv run uvicorn archscope_api.main:app --reload  # API at http://localhost:8000/docs
cd apps/web && npm ci && npm run dev            # web app at http://localhost:3000 (sign in there)
uv run streamlit run Home.py                    # legacy app, same domain code (being retired)
```

**Checks** (exactly what CI runs):

```bash
uv run ruff check packages apps && uv run ruff format --check packages apps
uv run mypy                       # --strict on domain, integrations, api
uv run lint-imports               # architecture contracts (see pyproject.toml)
uv run pytest                     # domain + golden parity, API, Streamlit smoke
uv run python -m archscope_api.openapi   # regenerate the contract after API changes
```

### Web app

[`apps/web`](apps/web) is the Next.js (React, TypeScript) front end:
sign-in and self sign-up, **Projects** (each client engagement), every
module for a project — Discovery Call Assistant, Deal Stage Planner,
Requirements Document, Joint Evaluation Plan, Portal Auditor, Property
Audit, Documentation Generator, Executive Report, Architecture Generator,
Architecture Diagram, Proposal & SOW Builder, Test Case Document, Project
Library — plus **Setup & API keys** and the **User guide** (its text lives
in `apps/web/src/lib/guide.ts`, which also feeds each page's sidebar
guide). The web app never links to Streamlit. Motion uses
[Framer Motion](https://motion.dev) and honors the OS "reduce motion"
setting.

The browser only talks to the web app: `/api/*` is proxied to the API
(`API_URL` in `apps/web/.env.local`, default `http://localhost:8000`), so
the session cookie is first-party and no CORS is involved.

- **No rule logic in the browser.** The page renders from
  `GET /api/v1/discovery/config` and asks `POST /api/v1/discovery/evaluate`
  (debounced as you type) which follow-ups, required tasks, checklist rows
  and build-order items the notes trigger — so the YAML files above stay
  the single source of truth. Exports go through `/api/v1/exports/*`.
- **Typed against the contract.** `src/lib/api-types.ts` is generated from
  `apps/api/openapi.json` (`npm run gen:api`); CI fails if it's stale
  (`npm run check:api`), then type-checks and builds
  (`.github/workflows/ci-web.yml`).
- **Saved per project.** Each module's work autosaves to the project
  (`PUT /api/v1/projects/{id}/state/{module}`) with a version number, so
  two people editing at once get a "changed elsewhere — reload" prompt
  instead of silently overwriting each other. Exports can be downloaded or
  saved to the project library. The read-only HubSpot snapshot is pulled
  once per project and shared (module `portal`): the Portal Auditor,
  Property Audit, Documentation Generator, Executive Report and the
  live-portal Architecture Diagram all read it, and audit findings saved
  there are highlighted in the report and the diagram.

### Accounts, data and configuration (API)

- **Sign-in:** email + password (PBKDF2, 600k iterations). The session is
  an HttpOnly, SameSite=Lax cookie (Secure outside local development);
  only a SHA-256 of its token is stored, and signing out kills it.
  Every `/api/v1` route requires a session. Admins can also create
  accounts with `python -m archscope_api.cli create-user`; `set-password`
  resets one.
- **Self sign-up:** "Create an account" on the sign-in page asks for name,
  email and password (at least 10 characters), then emails a 6-digit code;
  the account exists only once the code is confirmed. Codes are stored as
  an HMAC, expire after 15 minutes, allow 5 attempts, and can be re-sent
  once a minute. "Forgot password?" uses the same code flow. Responses never
  reveal whether an email already has an account. A new user joins the
  workspace whose sign-up domains match their email
  (`python -m archscope_api.cli signup-domains --workspace "<name>" sonamation.com`),
  otherwise gets a workspace of their own as its owner. Turn sign-up off
  with `ARCHSCOPE_SIGNUP_ENABLED=false`.
- **Email:** set `ARCHSCOPE_SMTP_HOST`, `_PORT` (587), `_USERNAME`,
  `_PASSWORD`, `ARCHSCOPE_SMTP_SECURITY` (`starttls` / `ssl` / `none`) and
  `ARCHSCOPE_MAIL_FROM`; the legacy `FEEDBACK_SMTP_*` / `FEEDBACK_FROM`
  variables work too. Without SMTP, local and test environments write each
  email to `var/outbox/` (and log the code) instead of sending it; staging
  and production turn sign-up off until SMTP is configured.
- **Tenancy:** users belong to workspaces with a role (owner / admin /
  member); projects, documents and credentials are scoped to the
  workspace.
- **Credentials:** the HubSpot token and Anthropic key are set on the
  Setup page, stored encrypted (Fernet, `ARCHSCOPE_SECRET_KEY`), and never
  returned — only "connected" and the last 4 characters.
- **Storage:** SQLAlchemy 2.0 + Alembic migrations
  (`src/archscope_api/migrations`; `python -m archscope_api.cli migrate`).
  SQLite locally and in tests, PostgreSQL in staging / production. Saved
  documents' bytes go to a blob store (a directory today, `ARCHSCOPE_BLOB_DIR`).
- **Environment** (prefix `ARCHSCOPE_`): `DATABASE_URL`
  (`postgresql+psycopg://…` in production), `SECRET_KEY` (required outside
  local/test — `python -m archscope_api.cli secret-key`), `BLOB_DIR`,
  `SESSION_DAYS`, `ENVIRONMENT`.

**Golden parity.** `packages/domain/tests/golden/` pins every domain output
(structured results, and the extracted text of every .docx/.xlsx/.pdf) to
what the Streamlit-era code produced. The API tests replay the same inputs
over HTTP. If an output change is intended, regenerate with
`GOLDEN_UPDATE=1 uv run pytest packages/domain/tests/golden` and review the
fixture diff like code.

**Architecture rules** (import-linter, enforced in CI): the domain may not
import any framework, HTTP or database library; integrations may not
import the API; API services may not import HTTP schemas.

**API configuration** (environment, prefix `ARCHSCOPE_`): `ENVIRONMENT`
(`local`/`test`/`staging`/`production`; docs are off in production),
`CORS_ORIGINS`, `LOG_LEVEL`; plus `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`
for discovery drafting (a workspace key saved on the Setup page takes
precedence).

**Gemini for testing (free tier).** When a Gemini key is set — "Gemini API
key" on the Setup page, or `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the
environment — discovery drafting uses Google Gemini instead of Claude; remove
the key to switch back. Get a free key at https://aistudio.google.com/apikey.
Models are tried most accurate first, each with its own free quota:
`gemini-3.8-flash` (the strongest model on the free tier — Gemini 3.1 Pro
isn't free), then `gemini-2.5-pro`, then `gemini-3.6-flash`. A model whose
free quota is used up (or that the key can't use) is skipped before any text
streams, so one document always comes from one model. Override the list with
`GEMINI_MODELS` (comma-separated). Free quotas reset at midnight Pacific. HubSpot calls use the workspace's stored token; an
`X-HubSpot-Token` request header overrides it for scripts.

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
