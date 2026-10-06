# ArchitectureScope User Guide

<!--
This file is the in-app guide. Every "## " heading is one guide section.
Sections whose heading matches a page title exactly (e.g. "## Portal Auditor")
also appear in that page's sidebar under "Guide for this page" — keep those
headings in sync with the page titles in Home.py.
-->

## Quick start

ArchitectureScope helps HubSpot implementation specialists run a project from the first discovery call to the final hand-off. The left sidebar is ordered the way a project actually runs — work top to bottom.

1. **Setup & API keys** — paste your keys first (Step 0 in the sidebar).
   - **Anthropic API key** — needed only for the Discovery Call Assistant's AI drafting.
   - **HubSpot private app token** — needed only for pages that read a live portal (Portal Auditor, Property Audit, Documentation Generator).
   - Pages that need neither (Requirements Document, Architecture Generator, Proposal & SOW Builder, …) work with no keys at all.
2. **Discover** — run the call with the Discovery Call Assistant, then formalize what you learned in the Requirements Document and Joint Evaluation Plan.
3. **Assess** — if the client already has a HubSpot portal, audit it.
4. **Design** — generate the architecture blueprint and diagram.
5. **Propose** — build the proposal / Statement of Work.
6. **Deliver & test** — track QA / UAT in the Test Case Document.
7. **Save as you go** — every page's **Save to Project Library** button files the output under the project name.

**Read-only against HubSpot.** The app never creates, updates, or deletes anything in a connected portal.

**Keys stay private.** Keys pasted on the Setup page live only in this browser session's memory — never written to disk or logged. Closing or reloading the tab clears them (and any unsaved work).

**Using the guide.** This page holds the full guide. On every other page, open **Guide for this page** at the bottom of the sidebar for that page's instructions.

## The process, step by step

| Step | Page | Needs | You get |
|---|---|---|---|
| 0 · Start here | Setup & API keys | — | Keys connected for this session |
| 1 · Discover | Discovery Call Assistant | Anthropic key (to generate) | Business-analysis doc, client explainer |
| 1 · Discover | Requirements Document | — | WRD (.docx/.xlsx/.csv/.pdf) |
| 1 · Discover | Joint Evaluation Plan | — | JEP (.docx/.xlsx/.csv/.pdf) |
| 2 · Assess | Portal Auditor | HubSpot token | Best-practice findings |
| 2 · Assess | Property Audit | HubSpot token | Keep/Review/Remove workbook + PDF |
| 2 · Assess | Documentation Generator | HubSpot token | Data dictionary & documentation pack |
| 2 · Assess | Executive Report | A portal pull (above) | Client + internal reports |
| 3 · Design | Architecture Generator | — | Proposed blueprint |
| 3 · Design | Architecture Diagram | A blueprint or portal pull | Editable object diagram |
| 4 · Propose | Proposal & SOW Builder | — (imports WRD/JEP) | Branded proposal / SOW PDF |
| 5 · Deliver & test | Test Case Document | — (imports WRD) | QA/UAT test log |
| Anytime | Project Library | — | Everything saved, by project |

**New build, no existing portal?** Skip Step 2.

**How pages share work.** Within one browser session, later steps reuse earlier ones: one portal pull feeds every Step 2 page plus the diagram; the WRD's requirements can prefill the Test Case Document and the Proposal & SOW Builder; the business analysis's recommended hubs pre-select the client explainer.

## Setup & API keys

**Anthropic API key** (Discovery Call Assistant only)

1. Sign in at **console.anthropic.com** → **API Keys** → **Create Key**.
2. Copy the key (it starts with `sk-ant-`) and paste it into **Anthropic API key**, then press **Enter**.
3. Click **Test connection** to confirm it works.

**HubSpot private app token** (Portal Auditor, Property Audit, Documentation Generator)

1. In the client's portal: **Settings → Integrations → Private Apps** (newer portals: **Development → Legacy apps**).
2. **Create a private app**, name it e.g. "ArchitectureScope (read-only)".
3. On **Scopes**, add the read scopes listed on the Setup page — no write scopes are needed.
4. **Create app**, copy the access token, paste it into **HubSpot private app access token**, press **Enter**, then **Test connection**.

**For regular use**, put both in a `.env` file in the project folder instead (`HUBSPOT_TOKEN=…` and `ANTHROPIC_API_KEY=…`; copy `.env.example`). The app loads it at startup.

A pasted key can be removed with **Forget this key**.

## Discovery Call Assistant

Use it **live, during the discovery call**.

1. Enter the **Client / project name** and the client's **business type** (e.g. "multi-location dental practice").
2. On **1 · Business analysis**, jot answers under **Goals**, **Data**, **Processes**, and **Solutions Design**. Shorthand and out-of-order notes are fine. Use **Edge cases / flags** for compliance, multi-location/multi-entity, or anything the client contradicted.
3. Leave unknowns blank — the AI never guesses. Every blank becomes a specific item under **Open Questions & Gaps**, which is your follow-up checklist.
4. After the call, click **Generate business analysis**. Review it under **Preview**, fix anything under **Edit text**, then download (.docx / .pdf / .md) or **Save to Project Library**.
5. Switch to **2 · Client explainer**, click **Use the hubs recommended in the business analysis** (or pick hubs yourself), and **Generate client explainer** — a plain-language page you can send the client.

**Tips**

- Notes survive switching pages, but not closing the tab. Use **Back up, restore, or reset call notes** to download a backup mid-call; restore it from the same place.
- **Start a new call** clears every note and draft before the next client.
- The business analysis's **Preliminary Scope Signals** section is written as input for the Proposal & SOW Builder.
- Needs an Anthropic API key (Setup). Notes are sent to Anthropic only when you click a Generate button.

## Requirements Document

The Written Requirements Document (WRD) formalizes what you learned in discovery, in HubSpot's own WRD structure.

1. Enter the **Project name** and the project's **Purpose** and **Goals**.
2. List numbered **Customer Requirements** — order matters; the Test Case Document and Proposal & SOW Builder can import them.
3. Add the client's own **Project Definitions** (terminology), **Known Challenges or Risks**, a draft **Project Plan**, **Open Questions**, and **Appendix** links.
4. Every table accepts added/deleted rows. Export as .docx / .xlsx / .csv / .pdf, or **Save to Project Library**.

Tip: the discovery business analysis's **Open Questions & Gaps** and **Solutions Design — Requirements** sections map directly onto this page.

## Joint Evaluation Plan

Tracks what has to happen, when, and who's involved while the client evaluates.

1. Fill in the solutions-partner contact and the **team roster**.
2. Add **milestones** with target date, status, owner, and outcome.
3. Record **technical needs**, **business needs**, and open **questions**.
4. Export or **Save to Project Library**. The Proposal & SOW Builder can import it.

## Portal Auditor

Assesses a **live portal** against best practice. Needs a HubSpot token (Setup).

1. Click **Pull from portal** (schemas, properties, pipelines, workflows, owners, teams).
2. Click **Run audit**.
3. Filter findings by severity and area; download CSV / Markdown or **Save to Project Library**.

Checks: duplicate / near-duplicate properties, unused properties, required properties missing on records, orphaned custom-object records, risky workflows, team/permission anomalies, and naming drift. Record-level checks sample records rather than reading everything, and each finding says so.

The pull is shared with Property Audit, Documentation Generator, Executive Report, and Architecture Diagram — no need to pull again.

## Property Audit

Rates **every property on every object** Keep / Review / Remove candidate. Needs a HubSpot token.

1. **Pull from portal** (or reuse the Portal Auditor's pull), then **Run property audit**.
2. Download the color-coded **.xlsx** workbook (Summary, Flagged for Action, All Properties, How to use) and the PDF report.

Ratings use a sampled fill rate plus workflow references. Native HubSpot properties are always Keep. Forms, lists, reports, and dashboards aren't read, so "Uses" can undercount. Nothing is ever deleted — a person makes every call.

## Documentation Generator

Documents what exists in a live portal. Needs a HubSpot token.

1. **Pull from portal** (or reuse an earlier pull).
2. Preview the data dictionary, workflow inventory, association map, pipelines & stages, and roles & permissions.
3. Export as Markdown or .docx.

Also useful again at hand-off, to document the finished build.

## Executive Report

A plain-language summary of a pulled portal and its audit findings. Makes no API calls of its own.

1. Pull a portal (Portal Auditor / Documentation Generator) and ideally run the Portal Auditor's audit first.
2. Optionally enter a client/project name.
3. Download the **Client report** (polished, capped examples) or the **Internal report** (every finding).

## Architecture Generator

Turns a project's requirements into a proposed HubSpot architecture. No keys needed.

1. Click **Load sample project** to see a full example, or fill in objects, pipelines, regions/currencies, integrations, record volumes, and hubs in scope.
2. Click **Generate blueprint**: custom objects, property data dictionary, associations, pipeline stages, naming convention, and suggested automations with overwrite-risk flags.
3. Export Markdown / JSON, or open it in the Architecture Diagram.

## Architecture Diagram

Draws the blueprint and/or live portal as an editable object diagram, with audit findings highlighted.

1. Pick the source (a live portal pull is preferred; otherwise the blueprint).
2. Fix anything in the **objects** and **connections** tables — the diagram redraws as you edit.
3. Use **Focus diagram on** to show a subset of objects.
4. Export `.drawio` (opens in diagrams.net for drag-and-drop editing), PNG, and table data.

## Proposal & SOW Builder

Builds a SonaMation-branded proposal and/or Statement of Work PDF.

1. **Import** the Requirements Document and Joint Evaluation Plan (they must have been opened this session).
2. Work through **Technical**, **Scope** (In Scope / Out of Scope / Optional Add-on / Client Responsibility), **Management**, and **Cost**.
3. On **Review & Generate**, check the warnings and download the PDF, or save a reusable `.json` template.

Tip: use the discovery business analysis's **Preliminary Scope Signals** to decide what goes in, what is explicitly excluded, and what to offer as add-ons. The full manual is under **Downloads** on the User guide page.

## Test Case Document

Tracks QA and UAT — one row per test case.

1. Optionally click **Load requirements** to start from the Requirements Document's Customer Requirements.
2. Record steps, expected/actual results, test round, and feedback.
3. Export or **Save to Project Library**.

## Project Library

Everything saved from any page, organized by project and document type, each file dated.

1. Pick a project.
2. Re-download or delete any saved file; some document types show a visual preview.

Files are stored locally in the `project_library/` folder.

## Troubleshooting

- **Found a bug or have an idea?** Click the orange **Feedback** button in the bottom-right corner of any page, describe it, attach screenshots with the paperclip, and press send. It goes straight to the app owner.

- **"Missing scope or invalid token"** — the HubSpot private app lacks a read scope, or the token was mistyped. Compare against the scope table on the Setup page.
- **"The Anthropic API key was rejected"** — re-copy the key from console.anthropic.com and paste it again on Setup.
- **A page lost my work** — closing or reloading the browser tab clears the session. Save to the Project Library (or, on the Discovery Call Assistant, download a notes backup) as you go.
- **Save to Project Library is greyed out** — enter a project name on that page first.
- **The app won't start** — run `pip install -r requirements.txt`, then `streamlit run Home.py` from the project folder.
