"""Setup & API keys — the app's landing page (first in the sidebar).

Connecting keys is the one thing a new user has to do before most pages
work, so it's the first stop: paste the Anthropic key and/or HubSpot token
here once, then follow the numbered process below (and in the sidebar).
Routed to by Home.py via st.navigation.
"""

from __future__ import annotations

import anthropic
import streamlit as st

from core.connections import anthropic_key_input, get_anthropic_key, hubspot_token_input
from core.discovery import model_id
from core.hubspot_client import HubSpotAPIError, HubSpotClient, HubSpotScopeError, get_token
from core.theme import inject_global_css, render_hero, render_page_header

st.set_page_config(page_title="ArchitectureScope — Setup", layout="wide")
inject_global_css()

render_hero(
    title_html="Run a HubSpot project from discovery to hand-off",
    subtitle=(
        "Start by connecting your API keys below. Then work down the sidebar in order: "
        "discover, assess, design, propose, deliver."
    ),
    cta_label="Go to Step 1 — Discovery",
    cta_href="/Discovery_Call_Assistant",
)

render_page_header(
    "Step 0 · Connect your API keys",
    "Each key is only needed for the pages listed under it — skip any you won't use. Pasted keys are "
    "kept in this browser session's memory only: never written to disk, never logged.",
)

ai_col, hs_col = st.columns(2)

with ai_col:
    with st.container(border=True):
        st.markdown("### Anthropic API key")
        st.caption("Needed for: **Discovery Call Assistant** (drafts the business analysis and client explainer).")
        anthropic_key_input()
        if get_anthropic_key() and st.button("Test connection", key="test_anthropic"):
            try:
                anthropic.Anthropic(api_key=get_anthropic_key()).models.retrieve(model_id())
                st.success(f"Anthropic key works — {model_id()} is available.")
            except anthropic.AuthenticationError:
                st.error("Anthropic rejected this key. Re-copy it and paste it again.")
            except anthropic.NotFoundError:
                st.error(f"The key works, but this account can't use {model_id()}.")
            except anthropic.APIConnectionError:
                st.error("Couldn't reach the Anthropic API. Check your internet connection.")
            except anthropic.APIStatusError as exc:
                st.error(f"Anthropic API error ({exc.status_code}): {exc.message}")
        with st.expander("How do I get an Anthropic API key?"):
            st.markdown(
                "1. Sign in at [console.anthropic.com](https://console.anthropic.com).\n"
                "2. Open **API Keys** → **Create Key**, and name it (e.g. \"ArchitectureScope\").\n"
                "3. Copy the key (starts with `sk-ant-`), paste it above, and press **Enter**.\n\n"
                "Call notes are sent to Anthropic only when you click a **Generate** button on the "
                "Discovery Call Assistant."
            )

with hs_col:
    with st.container(border=True):
        st.markdown("### HubSpot private app token")
        st.caption(
            "Needed for: **Portal Auditor**, **Property Audit**, **Documentation Generator** "
            "(read-only access to a live portal)."
        )
        hubspot_token_input()
        if get_token() and st.button("Test connection", key="test_hubspot"):
            try:
                HubSpotClient().get_properties("contacts")
                st.success("HubSpot token works — the portal's contact properties are readable.")
            except HubSpotScopeError as exc:
                st.error(f"Missing scope or invalid token: {exc}")
            except HubSpotAPIError as exc:
                st.error(f"HubSpot API error: {exc}")
        with st.expander("How do I get a HubSpot token?"):
            st.markdown(
                "1. In HubSpot, go to **Settings → Integrations → Private Apps** (newer portals: "
                "**Development → Legacy apps**).\n"
                "2. Click **Create a private app** and name it (e.g. \"ArchitectureScope (read-only)\").\n"
                "3. On the **Scopes** tab, add the read scopes below — this tool never writes to "
                "your portal, so no write scopes are needed.\n"
                "4. Click **Create app**, copy the **access token**, paste it above, and press **Enter**.\n\n"
                "Full walkthrough: "
                "[developers.hubspot.com/docs/api/private-apps](https://developers.hubspot.com/docs/api/private-apps)."
            )
            st.markdown(
                "**Required scopes** (exact names occasionally shift in HubSpot's scope picker — "
                "if a pull fails with a scope error, the app tells you which one's likely missing):\n\n"
                "| Used for | Scopes |\n"
                "|---|---|\n"
                "| Standard object schemas & properties | `crm.schemas.contacts.read`, "
                "`crm.schemas.companies.read`, `crm.schemas.deals.read`, `tickets` |\n"
                "| Custom object schemas & properties | `crm.schemas.custom.read` |\n"
                "| Record sampling (unused/required property & orphan checks) | "
                "`crm.objects.contacts.read`, `crm.objects.companies.read`, `crm.objects.deals.read`, "
                "`crm.objects.tickets.read`, `crm.objects.custom.read` |\n"
                "| Pipelines | covered by the object read scopes above |\n"
                "| Workflows (legacy Automation API) | `automation` |\n"
                "| Owners | `crm.objects.owners.read` |\n"
                "| Teams | `settings.users.teams.read` |\n\n"
                "You can grant a subset — pages report what they couldn't pull as a warning "
                "rather than failing outright."
            )

st.caption(
    "For regular use, put `ANTHROPIC_API_KEY=…` and `HUBSPOT_TOKEN=…` in a `.env` file in the project "
    "folder (copy `.env.example`) — the app picks them up at startup. Nothing here ever writes to HubSpot."
)

st.divider()

render_page_header(
    "Then follow the process",
    "The sidebar lists every page in this same order. Not sure where to start? Open the user guide.",
)
st.page_link("app_pages/12_User_Guide.py", label="Open the user guide")

STEPS = [
    (
        "1 · Discover",
        "Run the discovery call, then formalize what you learned.",
        [
            ("app_pages/11_Discovery_Call_Assistant.py", "Discovery Call Assistant", "Live call notes → business analysis and client explainer."),
            ("app_pages/6_Requirements_Document.py", "Requirements Document", "Purpose, numbered requirements, terminology, risks, open questions."),
            ("app_pages/7_Joint_Evaluation_Plan.py", "Joint Evaluation Plan", "Team, milestones, technical and business needs."),
        ],
    ),
    (
        "2 · Assess the current portal",
        "Only if the client already uses HubSpot. Needs the HubSpot token.",
        [
            ("app_pages/2_Portal_Auditor.py", "Portal Auditor", "Best-practice checks: duplicates, unused fields, risky workflows, drift."),
            ("app_pages/2b_Property_Audit.py", "Property Audit", "Keep / Review / Remove rating for every property."),
            ("app_pages/3_Documentation_Generator.py", "Documentation Generator", "Data dictionary, workflows, associations, pipelines, teams."),
            ("app_pages/4_Executive_Report.py", "Executive Report", "Plain-language client and internal reports."),
        ],
    ),
    (
        "3 · Design",
        "Turn the requirements into a HubSpot architecture.",
        [
            ("app_pages/1_Architecture_Generator.py", "Architecture Generator", "Objects, properties, associations, pipelines, naming."),
            ("app_pages/5_Architecture_Diagram.py", "Architecture Diagram", "Editable diagram; export to diagrams.net."),
        ],
    ),
    (
        "4 · Propose",
        "Price and scope the work.",
        [
            ("app_pages/10_Proposal_SOW_Builder.py", "Proposal & SOW Builder", "Branded proposal / Statement of Work PDF."),
        ],
    ),
    (
        "5 · Deliver & test",
        "Build, then prove it works.",
        [
            ("app_pages/8_Test_Case_Document.py", "Test Case Document", "QA / UAT test cases and results."),
        ],
    ),
]

for step_title, step_caption, pages in STEPS:
    with st.container(border=True):
        st.markdown(f"### {step_title}")
        st.caption(step_caption)
        cols = st.columns(len(pages))
        for col, (path, label, blurb) in zip(cols, pages):
            with col:
                st.page_link(path, label=label)
                st.caption(blurb)

st.page_link("app_pages/9_Project_Library.py", label="Project Library — everything saved, by project (use anytime)")
