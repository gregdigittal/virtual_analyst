from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock


def _current_period() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m")


_usage: dict[tuple[str, str], dict[str, int | float]] = {}
_usage_lock = Lock()


def get_usage(tenant_id: str, period: str | None = None) -> dict[str, int | float]:
    p = period or _current_period()
    with _usage_lock:
        return dict(_usage.get((tenant_id, p), {"llm_tokens_total": 0, "llm_calls": 0, "llm_estimated_usd": 0.0}))


def add_usage(tenant_id: str, tokens: int, cost_estimate_usd: float, period: str | None = None) -> None:
    p = period or _current_period()
    with _usage_lock:
        key = (tenant_id, p)
        if key not in _usage:
            _usage[key] = {"llm_tokens_total": 0, "llm_calls": 0, "llm_estimated_usd": 0.0}
        _usage[key]["llm_tokens_total"] = int(_usage[key]["llm_tokens_total"]) + tokens
        _usage[key]["llm_calls"] = int(_usage[key]["llm_calls"]) + 1
        _usage[key]["llm_estimated_usd"] = float(_usage[key]["llm_estimated_usd"]) + cost_estimate_usd


def check_limit(tenant_id: str, limit: int, period: str | None = None) -> bool:
    usage = get_usage(tenant_id, period)
    return int(usage["llm_tokens_total"]) < limit


def reset_usage() -> None:
    with _usage_lock:
        _usage.clear()
