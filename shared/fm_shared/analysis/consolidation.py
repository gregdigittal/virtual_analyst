"""
Consolidation engine: FX translation, line-by-line addition, proportional/equity method,
intercompany eliminations, NCI. Used for org-structure consolidated runs.
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass
class EntityResult:
    entity_id: str
    currency: str
    statements: dict[str, Any]  # IS/BS/CF from engine run
    kpis: dict[str, Any]
    ownership_pct: float  # % owned by parent (0-100)
    consolidation_method: str  # full | proportional | equity_method | not_consolidated
    withholding_tax_rate: float = 0.0  # for intercompany recipient side


@dataclasses.dataclass
class IntercompanyElimination:
    from_entity_id: str
    to_entity_id: str
    link_type: str
    amount_per_period: list[float]
    withholding_tax_per_period: list[float]
    interest_rate: float = 0.05  # for link_type=='loan': rate from amount_or_rate or default


@dataclasses.dataclass
class ConsolidatedResult:
    org_id: str
    reporting_currency: str
    consolidated_is: dict[str, Any]
    consolidated_bs: dict[str, Any]
    consolidated_cf: dict[str, Any]
    consolidated_kpis: dict[str, Any]
    entity_results: list[EntityResult]
    eliminations: list[IntercompanyElimination]
    fx_rates_used: dict[tuple[str, str], float]  # (from_ccy, to_ccy) -> rate
    minority_interest: dict[str, Any]  # NCI per period
    integrity: dict[str, Any]


def _get_period_values(stmt: dict[str, Any], horizon: int) -> dict[str, list[float]]:
    """Extract line label -> list of values for horizon periods from statement structure."""
    out: dict[str, list[float]] = {}
    if isinstance(stmt, list):
        for row in stmt:
            if not isinstance(row, dict):
                continue
            label = row.get("label") or row.get("name") or ""
            vals: list[float] = []
            for t in range(horizon):
                key = f"period_{t}"
                if key in row:
                    try:
                        vals.append(float(row[key]))
                    except (TypeError, ValueError):
                        vals.append(0.0)
                elif "values" in row and isinstance(row["values"], (list, tuple)) and t < len(row["values"]):
                    try:
                        vals.append(float(row["values"][t]))
                    except (TypeError, ValueError):
                        vals.append(0.0)
                else:
                    vals.append(0.0)
            if len(vals) < horizon:
                vals.extend([0.0] * (horizon - len(vals)))
            out[label] = vals
    elif isinstance(stmt, dict):
        for label, arr in stmt.items():
            if isinstance(arr, (list, tuple)) and len(arr) >= horizon:
                out[str(label)] = [float(arr[t]) if t < len(arr) else 0.0 for t in range(horizon)]
            else:
                out[str(label)] = [0.0] * horizon
    return out


def _dict_to_period_series(data: dict[str, list[float]], horizon: int) -> list[dict[str, Any]]:
    """Convert line->values back to list of row dicts with period_0, period_1, ..."""
    return [
        {"label": label, **{f"period_{t}": data[label][t] for t in range(horizon)}}
        for label in sorted(data.keys())
    ]


def _rate_key(from_ccy: str, to_ccy: str) -> tuple[str, str]:
    return (from_ccy, to_ccy)


def _get_rate(
    fx_rates: dict[tuple[str, str], float],
    from_ccy: str,
    to_ccy: str,
    integrity: dict[str, Any] | None = None,
) -> float:
    if from_ccy == to_ccy:
        return 1.0
    key = _rate_key(from_ccy, to_ccy)
    if key in fx_rates:
        return fx_rates[key]
    inv = _rate_key(to_ccy, from_ccy)
    if inv in fx_rates:
        return 1.0 / fx_rates[inv]
    if integrity is not None and "warnings" in integrity:
        integrity["warnings"].append(f"Missing FX rate for {from_ccy}/{to_ccy}, using 1.0")
    return 1.0  # fallback no translation


def translate_statements(
    statements: dict[str, Any],
    from_currency: str,
    to_currency: str,
    fx_avg_rates: dict[tuple[str, str], float],
    fx_closing_rates: dict[tuple[str, str], float] | None,
    horizon: int,
    integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """FX translate a single entity's statements. IAS 21/ASC 830: average rate for IS/CF, closing rate for BS. CTA in translation_reserve."""
    if fx_closing_rates is None:
        fx_closing_rates = fx_avg_rates
    avg_rate = _get_rate(fx_avg_rates, from_currency, to_currency, integrity)
    closing_rate = _get_rate(fx_closing_rates, from_currency, to_currency, integrity)
    if avg_rate == 1.0 and closing_rate == 1.0:
        out: dict[str, Any] = dict(statements)
        out.setdefault("translation_reserve", [0.0] * horizon)
        return out
    out = {}
    for key in ("income_statement", "cash_flow"):
        if key in statements:
            data = _get_period_values(statements[key], horizon)
            scaled = {label: [v * avg_rate for v in vals] for label, vals in data.items()}
            out[key] = _dict_to_period_series(scaled, horizon)
        else:
            out[key] = statements.get(key, [])
    if "balance_sheet" in statements:
        bs_data = _get_period_values(statements["balance_sheet"], horizon)
        bs_scaled = {label: [v * closing_rate for v in vals] for label, vals in bs_data.items()}
        out["balance_sheet"] = _dict_to_period_series(bs_scaled, horizon)
    else:
        out["balance_sheet"] = statements.get("balance_sheet", [])
    # CTA: equity at closing - (opening equity at closing + net income at avg)
    is_data = _get_period_values(out.get("income_statement", {}), horizon)
    bs_data = _get_period_values(out.get("balance_sheet", {}), horizon)
    equity_line = next((k for k in bs_data if "equity" in k.lower()), None)
    net_income_line = next((k for k in is_data if "net" in k.lower() and "income" in k.lower()), None)
    equity_vals = bs_data[equity_line] if equity_line else [0.0] * horizon
    ni_vals = is_data[net_income_line] if net_income_line else [0.0] * horizon
    cta: list[float] = [0.0] * horizon
    for t in range(horizon):
        bs_equity_closing = equity_vals[t] if t < len(equity_vals) else 0.0
        ni_avg = (ni_vals[t] if t < len(ni_vals) else 0.0)
        opening_equity_closing = (equity_vals[t - 1] if t > 0 and (t - 1) < len(equity_vals) else 0.0)
        cta[t] = bs_equity_closing - (opening_equity_closing + ni_avg)
    out["translation_reserve"] = cta
    return out


def consolidate(
    entity_results: list[EntityResult],
    eliminations: list[IntercompanyElimination],
    reporting_currency: str,
    fx_avg_rates: dict[tuple[str, str], float],
    minority_interest_treatment: str,
    horizon: int,
    eliminate_intercompany: bool = True,
    org_id: str = "",
    fx_closing_rates: dict[tuple[str, str], float] | None = None,
) -> ConsolidatedResult:
    """
    Consolidate entity results: FX translate (avg for IS/CF, closing for BS), then sum by consolidation method,
    apply eliminations, compute NCI. Statements format: dict with income_statement,
    balance_sheet, cash_flow (list of {label, period_0, ...} or dict label->[values]).
    """
    if fx_closing_rates is None:
        fx_closing_rates = fx_avg_rates
    integrity: dict[str, Any] = {"warnings": [], "errors": []}
    # Entity period mismatch: warn if entities have different effective period counts
    def _infer_period_count(st: dict[str, Any]) -> int | None:
        for key in ("income_statement", "balance_sheet", "cash_flow"):
            part = st.get(key)
            if isinstance(part, list) and part and isinstance(part[0], dict):
                row = part[0]
                period_keys = [k for k in row if isinstance(k, str) and k.startswith("period_")]
                if period_keys:
                    return len(period_keys)
            if isinstance(part, dict) and part:
                first = next(iter(part.values()), None)
                if isinstance(first, (list, tuple)):
                    return len(first)
        return None
    periods_per_entity: list[tuple[str, int]] = []
    for ent in entity_results:
        n = _infer_period_count(ent.statements)
        if n is not None:
            periods_per_entity.append((ent.entity_id, n))
    if len(periods_per_entity) >= 2:
        counts = {n for _, n in periods_per_entity}
        if len(counts) > 1:
            integrity["warnings"].append(
                "entity_period_mismatch: entities have different period counts: "
                + ", ".join(f"{eid}={n}" for eid, n in periods_per_entity)
            )
    translated: list[tuple[EntityResult, dict[str, Any]]] = []
    for ent in entity_results:
        st = ent.statements
        if ent.currency != reporting_currency:
            st = translate_statements(st, ent.currency, reporting_currency, fx_avg_rates, fx_closing_rates, horizon, integrity)
        is_data = _get_period_values(st.get("income_statement", {}), horizon)
        bs_data = _get_period_values(st.get("balance_sheet", {}), horizon)
        cf_data = _get_period_values(st.get("cash_flow", {}), horizon)
        translated.append((ent, {"is": is_data, "bs": bs_data, "cf": cf_data}))

    full_entities = [(e, d) for e, d in translated if e.consolidation_method == "full"]
    prop_entities = [(e, d) for e, d in translated if e.consolidation_method == "proportional"]
    equity_entities = [(e, d) for e, d in translated if e.consolidation_method == "equity_method"]

    consolidated_is_data: dict[str, list[float]] = {}
    consolidated_bs_data: dict[str, list[float]] = {}
    consolidated_cf_data: dict[str, list[float]] = {}
    nci_profit_per_period: list[float] = [0.0] * horizon  # NCI share of profit (IS)
    nci_equity_per_period: list[float] = [0.0] * horizon  # NCI share of equity (BS)

    def _merge_into(target: dict[str, list[float]], source: dict[str, list[float]], horizon: int) -> None:
        for label, vals in source.items():
            if label not in target:
                target[label] = [0.0] * horizon
            for t in range(horizon):
                target[label][t] += vals[t] if t < len(vals) else 0.0

    # Full consolidation: 100% line sum; NCI share of profit (IS) and NCI share of equity (BS)
    for ent, data in full_entities:
        _merge_into(consolidated_is_data, data["is"], horizon)
        _merge_into(consolidated_bs_data, data["bs"], horizon)
        _merge_into(consolidated_cf_data, data["cf"], horizon)
        net_income_line = next((k for k in data["is"] if "net" in k.lower() and "income" in k.lower()), None)
        if net_income_line and ent.ownership_pct < 100:
            nci_share = (100 - ent.ownership_pct) / 100.0
            for t in range(horizon):
                ni = data["is"][net_income_line][t] if t < len(data["is"][net_income_line]) else 0.0
                nci_profit_per_period[t] += ni * nci_share
        if ent.ownership_pct < 100:
            nci_share = (100 - ent.ownership_pct) / 100.0
            equity_line = next((k for k in data["bs"] if "equity" in k.lower()), None)
            if equity_line:
                for t in range(horizon):
                    eq = data["bs"][equity_line][t] if t < len(data["bs"][equity_line]) else 0.0
                    nci_equity_per_period[t] += eq * nci_share

    # Proportional: sum at ownership_pct (no NCI)
    for ent, data in prop_entities:
        factor = ent.ownership_pct / 100.0
        for label, vals in data["is"].items():
            if label not in consolidated_is_data:
                consolidated_is_data[label] = [0.0] * horizon
            for t in range(horizon):
                consolidated_is_data[label][t] += (vals[t] if t < len(vals) else 0.0) * factor
        for label, vals in data["bs"].items():
            if label not in consolidated_bs_data:
                consolidated_bs_data[label] = [0.0] * horizon
            for t in range(horizon):
                consolidated_bs_data[label][t] += (vals[t] if t < len(vals) else 0.0) * factor
        for label, vals in data["cf"].items():
            if label not in consolidated_cf_data:
                consolidated_cf_data[label] = [0.0] * horizon
            for t in range(horizon):
                consolidated_cf_data[label][t] += (vals[t] if t < len(vals) else 0.0) * factor

    # Equity method: only "Share of profit of associate" and "Investment in associate"
    for ent, data in equity_entities:
        net_income_line = next((k for k in data["is"] if "net" in k.lower() and "income" in k.lower()), None)
        share_of_profit = [0.0] * horizon
        if net_income_line:
            for t in range(horizon):
                ni = data["is"][net_income_line][t] if t < len(data["is"][net_income_line]) else 0.0
                share_of_profit[t] = ni * (ent.ownership_pct / 100.0)
        key = f"Share of profit ({ent.entity_id})"
        if key not in consolidated_is_data:
            consolidated_is_data[key] = [0.0] * horizon
        for t in range(horizon):
            consolidated_is_data[key][t] += share_of_profit[t]
        equity_line = next((k for k in data["bs"] if "equity" in k.lower() or "equity" in k), None)
        inv_value = [0.0] * horizon
        if equity_line:
            for t in range(horizon):
                eq = data["bs"][equity_line][t] if t < len(data["bs"][equity_line]) else 0.0
                inv_value[t] = eq * (ent.ownership_pct / 100.0)
        inv_key = f"Investment in associate ({ent.entity_id})"
        if inv_key not in consolidated_bs_data:
            consolidated_bs_data[inv_key] = [0.0] * horizon
        for t in range(horizon):
            consolidated_bs_data[inv_key][t] += inv_value[t]

    # Intercompany eliminations (IS, BS, CF)
    for elim in eliminations:
        if not eliminate_intercompany:
            continue
        for t in range(horizon):
            amt = elim.amount_per_period[t] if t < len(elim.amount_per_period) else 0.0
            wt = elim.withholding_tax_per_period[t] if t < len(elim.withholding_tax_per_period) else 0.0
            net_elim = amt - wt
            if elim.link_type in ("management_fee", "royalty", "trade"):
                if "Intercompany revenue" not in consolidated_is_data:
                    consolidated_is_data["Intercompany revenue"] = [0.0] * horizon
                if "Intercompany expense" not in consolidated_is_data:
                    consolidated_is_data["Intercompany expense"] = [0.0] * horizon
                consolidated_is_data["Intercompany revenue"][t] -= net_elim
                consolidated_is_data["Intercompany expense"][t] -= net_elim
                consolidated_bs_data.setdefault("Intercompany receivable", [0.0] * horizon)
                consolidated_bs_data.setdefault("Intercompany payable", [0.0] * horizon)
                consolidated_bs_data["Intercompany receivable"][t] -= net_elim
                consolidated_bs_data["Intercompany payable"][t] -= net_elim
                consolidated_cf_data.setdefault("Intercompany operating", [0.0] * horizon)
                consolidated_cf_data["Intercompany operating"][t] -= net_elim
            elif elim.link_type == "dividend":
                if "Dividend income" not in consolidated_is_data:
                    consolidated_is_data["Dividend income"] = [0.0] * horizon
                if "Dividend paid" not in consolidated_is_data:
                    consolidated_is_data["Dividend paid"] = [0.0] * horizon
                consolidated_is_data["Dividend income"][t] -= net_elim
                consolidated_is_data["Dividend paid"][t] -= net_elim
                consolidated_cf_data.setdefault("Dividends", [0.0] * horizon)
                consolidated_cf_data["Dividends"][t] -= net_elim
            elif elim.link_type == "loan":
                consolidated_bs_data.setdefault("Intercompany loan receivable", [0.0] * horizon)
                consolidated_bs_data.setdefault("Intercompany loan payable", [0.0] * horizon)
                consolidated_bs_data["Intercompany loan receivable"][t] -= amt
                consolidated_bs_data["Intercompany loan payable"][t] -= amt
                consolidated_is_data.setdefault("Intercompany interest income", [0.0] * horizon)
                consolidated_is_data.setdefault("Intercompany interest expense", [0.0] * horizon)
                rate = getattr(elim, "interest_rate", 0.05)
                interest = amt * rate
                consolidated_is_data["Intercompany interest income"][t] -= interest
                consolidated_is_data["Intercompany interest expense"][t] -= interest

    # NCI: IS = share of profit, BS = share of equity (IFRS 10 / ASC 810)
    if any(nci_profit_per_period):
        consolidated_is_data["NCI share of profit"] = nci_profit_per_period
    if any(nci_equity_per_period):
        consolidated_bs_data["Non-Controlling Interest"] = nci_equity_per_period

    consolidated_is = _dict_to_period_series(consolidated_is_data, horizon)
    consolidated_bs = _dict_to_period_series(consolidated_bs_data, horizon)
    consolidated_cf = _dict_to_period_series(consolidated_cf_data, horizon)

    return ConsolidatedResult(
        org_id=org_id,
        reporting_currency=reporting_currency,
        consolidated_is={"income_statement": consolidated_is},
        consolidated_bs={"balance_sheet": consolidated_bs},
        consolidated_cf={"cash_flow": consolidated_cf},
        consolidated_kpis={},
        entity_results=entity_results,
        eliminations=eliminations,
        fx_rates_used=dict(fx_avg_rates),
        minority_interest={"nci_profit": nci_profit_per_period, "nci_equity": nci_equity_per_period},
        integrity=integrity,
    )


def compute_intercompany_amounts(
    links: list[dict[str, Any]],
    entity_results: list[EntityResult],
    horizon: int,
    horizon_granularity: str = "annual",
) -> list[IntercompanyElimination]:
    """Derive per-period amounts for each intercompany link. horizon_granularity: 'monthly'|'quarterly'|'annual' (forecast period length)."""
    result: list[IntercompanyElimination] = []
    entity_by_id = {e.entity_id: e for e in entity_results}
    horizon_ppy = 12 if horizon_granularity == "monthly" else 4 if horizon_granularity == "quarterly" else 1
    for link in links:
        from_id = link.get("from_entity_id") or ""
        to_id = link.get("to_entity_id") or ""
        link_type = link.get("link_type") or "management_fee"
        amount_or_rate = link.get("amount_or_rate")
        frequency = (link.get("frequency") or "monthly").lower()
        withholding = link.get("withholding_tax_applicable") or False
        to_entity = entity_by_id.get(to_id)
        wt_rate = getattr(to_entity, "withholding_tax_rate", 0.0) if to_entity else 0.0
        wt_rate = float(wt_rate) if wt_rate is not None else 0.0

        link_ppy = 12 if frequency == "monthly" else 4 if frequency == "quarterly" else 1
        base = float(amount_or_rate) if amount_or_rate is not None else 0.0
        annual_total = base * link_ppy
        per_period_amount = annual_total / horizon_ppy if horizon_ppy else 0.0
        per_period = [per_period_amount] * horizon if base else [0.0] * horizon
        # For loan type, amount_or_rate is the interest rate (e.g. 0.05); use for interest calc
        interest_rate = 0.05
        if link_type == "loan" and amount_or_rate is not None:
            try:
                interest_rate = float(amount_or_rate)
            except (TypeError, ValueError):
                pass

        wt_per = [p * wt_rate for p in per_period] if withholding else [0.0] * horizon
        result.append(
            IntercompanyElimination(
                from_entity_id=from_id,
                to_entity_id=to_id,
                link_type=link_type,
                amount_per_period=per_period,
                withholding_tax_per_period=wt_per,
                interest_rate=interest_rate,
            )
        )
    return result
