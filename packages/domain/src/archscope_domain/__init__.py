"""ArchitectureScope domain — pure business logic for HubSpot solution
architecture: blueprint generation, portal audits, property audits,
reports, diagrams, proposals/SOWs, discovery, and document exports.

No web framework, database, or network code lives here. External reads go
through :mod:`archscope_domain.ports`; callers (the FastAPI service, the
legacy Streamlit app) supply the adapters.
"""
