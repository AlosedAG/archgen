"""The in-app guide: every sidebar page with instructions has a guide
section whose heading matches its title exactly (that's how the sidebar
finds it), and the guide parses into its expected sections."""

from __future__ import annotations

import re
from pathlib import Path

from core.guide import guide_sections, page_guide

REPO_ROOT = Path(__file__).resolve().parent.parent


def _page_titles() -> list[str]:
    source = (REPO_ROOT / "Home.py").read_text(encoding="utf-8")
    return re.findall(r'title="([^"]+)"', source)


def test_every_page_except_the_guide_itself_has_a_guide_section():
    missing = [t for t in _page_titles() if t != "User guide" and not page_guide(t)]
    assert not missing, f"docs/user_guide.md has no '## <title>' section for: {missing}"


def test_guide_has_overview_sections_and_strips_comments():
    sections = guide_sections()
    assert list(sections)[:2] == ["Quick start", "The process, step by step"]
    assert all("<!--" not in body for body in sections.values())


def test_unknown_page_has_no_guide():
    assert page_guide("Nope") == ""
