"""Budget template catalog (VA-P7-03): manufacturing, SaaS, services, wholesale."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_BUDGET_CATALOG: dict[str, Any] | None = None


def load_budget_catalog() -> dict[str, Any]:
    global _BUDGET_CATALOG
    if _BUDGET_CATALOG is None:
        path = Path(__file__).resolve().parent / "budget_templates.json"
        with open(path, encoding="utf-8") as f:
            _BUDGET_CATALOG = json.load(f)
    return _BUDGET_CATALOG


def get_budget_template(template_id: str) -> dict[str, Any] | None:
    catalog = load_budget_catalog()
    for t in catalog.get("templates", []):
        if t.get("template_id") == template_id:
            return t
    return None
