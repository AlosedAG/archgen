"""Write the committed OpenAPI contract: ``python -m archscope_api.openapi``.

``apps/api/openapi.json`` is the single source the web app's TypeScript
client is generated from. CI regenerates it and fails on any diff, so an
API change can't ship without its contract (and the client) changing too.
"""

from __future__ import annotations

import json
from pathlib import Path

from .main import create_app
from .settings import Settings

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


def render_openapi() -> str:
    # Built with docs enabled regardless of the caller's environment.
    spec = create_app(Settings(environment="local")).openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8")
    print(f"wrote {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
