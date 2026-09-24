"""Shared visual theme for the Streamlit app — SonaMation brand (deep
purple + orange accent, bold rounded headings).

Call ``inject_global_css()`` once near the top of every page, right after
``st.set_page_config``. Use ``render_page_header`` in place of a raw
``st.title`` + ``st.caption`` pair for a consistent branded heading, and
``render_hero`` for the purple gradient banner (Home page only).

``.streamlit/config.toml`` sets the native theme (colors/font) every
built-in widget already picks up automatically — sliders, checkboxes,
focus rings, the primary-color accent on ``type="primary"`` buttons. This
module layers a small, defensive CSS block on top for the things native
theming can't reach (the hero banner, pill-shaped buttons, heading
underline accent, sidebar background), targeting Streamlit's documented
``data-testid`` hooks rather than internal/minified class names so it
survives Streamlit version bumps.
"""

from __future__ import annotations

import streamlit as st

PURPLE_DARK = "#2A2058"
PURPLE = "#3D2E7C"
PURPLE_LIGHT = "#5B45B0"
ORANGE = "#F7791D"
ORANGE_HOVER = "#DD6A0F"
TEXT_DARK = "#14121F"
TEXT_BODY = "#3E3A4D"
BG_ALT = "#F6F5FA"
BORDER = "#E4E1EE"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

h1, h2, h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
    font-family: 'Poppins', 'Inter', sans-serif;
    color: {TEXT_DARK};
    font-weight: 700;
}}

/* ---- Buttons (primary + download) ---- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    background-color: {ORANGE};
    color: white;
    border: none;
    border-radius: 999px;
    padding: 0.55rem 1.6rem;
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(247, 121, 29, 0.35);
    transition: background-color 0.15s ease, transform 0.1s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
    background-color: {ORANGE_HOVER};
    color: white;
}}
.stButton > button:active, .stDownloadButton > button:active {{
    transform: translateY(1px);
}}
.stButton > button[kind="secondary"] {{
    background-color: white;
    color: {PURPLE};
    border: 1.5px solid {PURPLE};
    box-shadow: none;
}}
.stButton > button[kind="secondary"]:hover {{
    background-color: {BG_ALT};
    color: {PURPLE};
}}

/* ---- Page links (cross-module navigation) ---- */
[data-testid="stPageLink"] p {{
    font-weight: 600;
    color: {PURPLE};
}}
[data-testid="stPageLink"]:hover p {{
    color: {ORANGE};
}}

/* ---- Metrics ---- */
[data-testid="stMetricValue"] {{
    color: {PURPLE};
    font-weight: 800;
}}
[data-testid="stMetricLabel"] {{
    color: {TEXT_BODY};
    font-weight: 600;
}}

/* ---- Alerts / expanders / bordered containers ---- */
.stAlert {{
    border-radius: 12px;
}}
[data-testid="stExpander"] {{
    border-radius: 12px;
    border: 1px solid {BORDER};
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 16px !important;
}}

hr {{
    border-top: 2px solid {BORDER};
}}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {{
    background-color: {PURPLE_DARK};
}}
[data-testid="stSidebar"] * {{
    color: #F2F0FA;
}}
[data-testid="stSidebarNav"] a {{
    border-radius: 8px;
}}
[data-testid="stSidebarNav"] a:hover {{
    background-color: rgba(255, 255, 255, 0.08);
}}

/* ---- Branded section header (replaces st.title/st.caption) ---- */
.sm-page-title {{
    font-family: 'Poppins', 'Inter', sans-serif;
    font-size: 2.1rem;
    font-weight: 700;
    color: {TEXT_DARK};
    margin-bottom: 0.4rem;
}}
.sm-title-underline {{
    width: 64px;
    height: 4px;
    background-color: {ORANGE};
    border-radius: 2px;
    margin-bottom: 1rem;
}}
.sm-caption {{
    color: {TEXT_BODY};
    font-size: 1.02rem;
    line-height: 1.55;
    margin-bottom: 0.5rem;
}}

/* ---- Hero banner (Home page) ---- */
.sm-hero {{
    background: linear-gradient(120deg, {PURPLE_DARK} 0%, {PURPLE} 55%, {PURPLE_LIGHT} 100%);
    border-radius: 20px;
    padding: 3rem 2.5rem;
    margin-bottom: 1.75rem;
}}
.sm-hero-card {{
    background-color: rgba(20, 15, 40, 0.55);
    border-radius: 16px;
    padding: 2.25rem 2.5rem;
    max-width: 700px;
}}
.sm-hero-card h1 {{
    color: white;
    font-size: 2.5rem;
    line-height: 1.18;
    margin: 0 0 1rem 0;
}}
.sm-hero-card p {{
    color: #EDE9FA;
    font-size: 1.05rem;
    line-height: 1.6;
    margin-bottom: 1.5rem;
}}
.sm-hero-cta {{
    display: inline-block;
    background-color: {ORANGE};
    color: white !important;
    font-weight: 600;
    text-decoration: none;
    border-radius: 999px;
    padding: 0.65rem 1.8rem;
    box-shadow: 0 2px 6px rgba(247, 121, 29, 0.4);
}}
.sm-hero-cta:hover {{
    background-color: {ORANGE_HOVER};
}}
</style>
"""


def inject_global_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_page_header(title: str, caption: str = "") -> None:
    """Branded replacement for a plain ``st.title`` + ``st.caption`` pair:
    bold heading with the orange underline accent used throughout the app."""
    st.markdown(f'<div class="sm-page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sm-title-underline"></div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="sm-caption">{caption}</div>', unsafe_allow_html=True)


# ---- Audit report palette (Property Audit workbook + PDF export) --------
# Matches examples/RPG_property_audit.xlsx and examples/RPG_HubSpot_Audit_Report.pdf
# exactly, as (R, G, B) tuples so both openpyxl (ARGB hex) and fpdf2 (RGB
# tuple) exporters can share one source of truth for "same palette as the
# example" instead of two hand-copied color lists drifting apart.
AUDIT_HEADER_BG = (42, 26, 94)  # table header row / stat-tile accents
AUDIT_TITLE = (61, 43, 140)  # report/workbook title
AUDIT_SUBTITLE = (106, 100, 130)  # muted captions, internal-name mono text
AUDIT_BODY = (30, 26, 60)  # body text
AUDIT_MUTED = (150, 145, 168)  # footers, page numbers, axis labels
AUDIT_KEEP_BG = (222, 217, 242)  # light purple — Keep rating
AUDIT_REVIEW_BG = (245, 228, 195)  # light gold — Review rating
AUDIT_REMOVE_BG = (240, 210, 193)  # light peach — Remove candidate rating
AUDIT_CUSTOM_BADGE = (193, 90, 40)  # orange — "Custom = Yes" badge text


def argb(rgb: tuple[int, int, int]) -> str:
    """openpyxl ARGB hex string (``'FFrrggbb'``) for a theme RGB tuple."""
    return "FF{:02X}{:02X}{:02X}".format(*rgb)


def render_hero(title_html: str, subtitle: str, cta_label: str, cta_href: str) -> None:
    """Purple gradient hero banner (Home page only). ``cta_href`` is a
    same-app page path (e.g. ``/Architecture_Generator``) — rendered as a
    plain styled link rather than a Streamlit widget so it can live inside
    the translucent hero card; Streamlit multipage apps serve every page at
    its own URL, so a normal in-tab navigation works fine here."""
    st.markdown(
        f"""
        <div class="sm-hero">
          <div class="sm-hero-card">
            <h1>{title_html}</h1>
            <p>{subtitle}</p>
            <a class="sm-hero-cta" href="{cta_href}" target="_self">{cta_label}</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
