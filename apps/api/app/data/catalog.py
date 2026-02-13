from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CATALOG: dict[str, Any] | None = None


def load_catalog() -> dict[str, Any]:
    global _CATALOG
    if _CATALOG is None:
        path = Path(__file__).resolve().parent / "default_catalog.json"
        with open(path, encoding="utf-8") as f:
            _CATALOG = json.load(f)
    return _CATALOG


def get_template(template_id: str) -> dict[str, Any] | None:
    catalog = load_catalog()
    for t in catalog.get("templates", []):
        if t.get("template_id") == template_id:
            return t
    return None
