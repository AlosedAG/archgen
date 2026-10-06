"""The in-app user guide, read from ``docs/user_guide.md``.

The guide is one Markdown file split on its ``## `` headings. The User
Guide page renders all of it; the router shows the one section whose
heading matches the current page's title in that page's sidebar, so a
user never has to leave a page to read how it works.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
GUIDE_PATH = DOCS_DIR / "user_guide.md"

_COMMENT = re.compile(r"<!--.*?-->", re.S)


@lru_cache(maxsize=1)
def guide_sections() -> dict[str, str]:
    """Ordered ``{heading: body}`` for every ``## `` section of the guide."""
    text = _COMMENT.sub("", GUIDE_PATH.read_text(encoding="utf-8"))
    sections: dict[str, str] = {}
    for chunk in re.split(r"^## ", text, flags=re.M)[1:]:
        heading, _, body = chunk.partition("\n")
        sections[heading.strip()] = body.strip()
    return sections


def page_guide(page_title: str) -> str:
    """The guide section for a page, or ``""`` if it has none."""
    return guide_sections().get(page_title, "")
