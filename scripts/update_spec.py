"""Refresh the bundled spec (fallback when the live spec cannot be loaded).

    python scripts/update_spec.py

The server itself always tries the live spec first; this copy only matters
when api.es-go.de is unreachable at start-up. regenerate.yml runs this daily
and opens a pull request when the contract changed.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

SPEC_URL = "https://api.es-go.de/v1/openapi.json"
TARGET = Path(__file__).resolve().parent.parent / "src" / "esgo_mcp" / "openapi.json"


def main() -> None:
    with urllib.request.urlopen(SPEC_URL, timeout=30) as response:
        spec = json.load(response)
    TARGET.write_text(json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Spec written: {TARGET.name} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
