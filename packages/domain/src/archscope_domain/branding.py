"""Brand palette shared by every renderer (diagram, xlsx, PDF) and by the
Streamlit theme — one source of truth, with no UI-framework dependency.

SonaMation brand: deep purple + orange accent. The ``AUDIT_*`` colors
match ``examples/RPG_property_audit.xlsx`` and
``examples/RPG_HubSpot_Audit_Report.pdf`` exactly, as (R, G, B) tuples so
openpyxl (ARGB hex, via :func:`argb`) and fpdf2 (RGB tuples) share them.
"""

from __future__ import annotations

RGB = tuple[int, int, int]

PURPLE_DARK = "#2A2058"
PURPLE = "#3D2E7C"
PURPLE_LIGHT = "#5B45B0"
ORANGE = "#F7791D"
ORANGE_HOVER = "#DD6A0F"
TEXT_DARK = "#14121F"
TEXT_BODY = "#3E3A4D"
BG_ALT = "#F6F5FA"
BORDER = "#E4E1EE"

AUDIT_HEADER_BG: RGB = (42, 26, 94)  # table header row / stat-tile accents
AUDIT_TITLE: RGB = (61, 43, 140)  # report/workbook title
AUDIT_SUBTITLE: RGB = (106, 100, 130)  # muted captions, internal-name mono text
AUDIT_BODY: RGB = (30, 26, 60)  # body text
AUDIT_MUTED: RGB = (150, 145, 168)  # footers, page numbers, axis labels
AUDIT_KEEP_BG: RGB = (222, 217, 242)  # light purple — Keep rating
AUDIT_REVIEW_BG: RGB = (245, 228, 195)  # light gold — Review rating
AUDIT_REMOVE_BG: RGB = (240, 210, 193)  # light peach — Remove candidate rating
AUDIT_CUSTOM_BADGE: RGB = (193, 90, 40)  # orange — "Custom = Yes" badge text


def argb(rgb: RGB) -> str:
    """openpyxl ARGB hex string (``'FFrrggbb'``) for a palette RGB tuple."""
    return "FF{:02X}{:02X}{:02X}".format(*rgb)
