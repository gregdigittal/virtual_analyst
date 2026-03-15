"""
Three-statement generator: Income Statement, Balance Sheet, Cash Flow.
Uses engine time_series output + config assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.fm_shared.errors import EngineError
from shared.fm_shared.model.debt import calculate_debt_schedule, empty_debt_result
from shared.fm_shared.model.engine import _resolve_driver
from shared.fm_shared.model.funding_waterfall import apply_funding_waterfall
from shared.fm_shared.model.schemas import ModelConfig


@dataclass
class Statements:
    income_statement: list[dict[str, Any]]
    balance_sheet: list[dict[str, Any]]
    cash_flow: list[dict[str, Any]]
    periods: list[str]
    revenue_by_segment: dict[str, list[float]] = field(default_factory=dict)


class StatementImbalanceError(EngineError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code="ERR_ENG_STATEMENTS", context=details or {}, **kwargs)


_REVENUE_KEYWORDS = ("revenue", "sales", "income_from_operations")
_COGS_KEYWORDS = ("cogs", "cost_of_goods", "cost_of_sales", "direct_cost")


def _revenue_and_cogs_from_timeseries(
    time_series: dict[str, list[float]],
    blueprint_nodes: list,
    horizon: int,
) -> tuple[list[float], list[float]]:
    revenue = [0.0] * horizon
    cogs = [0.0] * horizon
    for node in blueprint_nodes:
        if node.get("type") != "output":
            continue
        nid = node["node_id"]
        if nid not in time_series:
            continue
        series = time_series[nid]
        classification = (node.get("classification") or node.get("statement_line") or "").lower()
        if not classification:
            label = (node.get("label") or "").lower()
            nid_lower = nid.lower()
            if any(k in label for k in _REVENUE_KEYWORDS) or any(k in nid_lower for k in _REVENUE_KEYWORDS):
                classification = "revenue"
            elif any(k in label for k in _COGS_KEYWORDS) or any(k in nid_lower for k in _COGS_KEYWORDS):
                classification = "cogs"
        if classification == "revenue":
            for t in range(horizon):
                revenue[t] += series[t]
        elif classification == "cogs":
            for t in range(horizon):
                cogs[t] += series[t]
    return revenue, cogs


def _fixed_opex_per_period(config: ModelConfig, horizon: int) -> list[float]:
    fixed: list[float] = []
    for t in range(horizon):
        total = 0.0
        for item in config.assumptions.cost_structure.fixed_costs:
            total += _resolve_driver(item.driver, t)
        fixed.append(total)
    return fixed


def _ar_ap_inv_days_per_period(
    config: ModelConfig, horizon: int
) -> list[tuple[float, float, float]]:
    wc = config.assumptions.working_capital
    out: list[tuple[float, float, float]] = []
    for t in range(horizon):
        ar = _resolve_driver(wc.ar_days, t)
        ap = _resolve_driver(wc.ap_days, t)
        inv = _resolve_driver(wc.inv_days, t)
        out.append((ar, ap, inv))
    return out


def _compute_da_per_period(config: ModelConfig, horizon: int) -> list[float]:
    """Straight-line depreciation per period from capex schedule. # IAS 16"""
    da: list[float] = [0.0] * horizon
    if config.assumptions.capex and config.assumptions.capex.items:
        for item in config.assumptions.capex.items:
            monthly_da = (item.amount - item.residual_value) / item.useful_life_months
            for t in range(item.month, min(item.month + item.useful_life_months, horizon)):
                da[t] += monthly_da
    return da


def _compute_equity_raises_per_period(
    config: ModelConfig, horizon: int, debt_result: Any
) -> list[float]:
    """Equity injections per period, including convertible debt conversions."""
    raises = [0.0] * horizon
    if config.assumptions.funding and config.assumptions.funding.equity_raises:
        for er in config.assumptions.funding.equity_raises:
            if 0 <= er.month < horizon:
                raises[er.month] += er.amount
    if config.assumptions.funding and config.assumptions.funding.debt_facilities:
        for fac in config.assumptions.funding.debt_facilities:
            if fac.converts_to_equity_month is not None and 0 <= fac.converts_to_equity_month < horizon:
                bal_list = debt_result.balance_per_period.get(fac.facility_id, [0.0] * horizon)
                if fac.converts_to_equity_month > 0:
                    conversion_amount = bal_list[fac.converts_to_equity_month - 1]
                else:
                    conversion_amount = sum(
                        d.amount for d in (fac.draw_schedule or []) if d.month == 0
                    )
                raises[fac.converts_to_equity_month] += conversion_amount
    return raises


def _build_income_statement(
    horizon: int,
    tax_rate: float,
    nol_enabled: bool,
    revenue: list[float],
    cogs: list[float],
    fixed_opex: list[float],
    da_per_month: list[float],
    interest: list[float],
    config: ModelConfig,
) -> list[dict[str, Any]]:
    """Build per-period income statement with NOL carry-forward. # IAS 12 — Income Taxes"""
    dividend_policy = (
        config.assumptions.funding.dividends
        if config.assumptions.funding and config.assumptions.funding.dividends
        else None
    )
    nol_balance = 0.0
    is_list: list[dict[str, Any]] = []
    for t in range(horizon):
        rev_t = revenue[t]
        cogs_t = cogs[t]
        gross = rev_t - cogs_t
        ebitda = gross - fixed_opex[t]
        ebit = ebitda - da_per_month[t]
        ebt = ebit - interest[t]
        nol_used = 0.0
        if nol_enabled and ebt > 0 and nol_balance > 0:
            nol_used = min(nol_balance, ebt)
            nol_balance -= nol_used
        taxable_income = max(0.0, ebt - nol_used)
        tax = taxable_income * tax_rate
        if nol_enabled and ebt < 0:
            nol_balance += abs(ebt)
        ni = ebt - tax
        dividend = 0.0
        if dividend_policy:
            if dividend_policy.policy == "fixed_amount":
                dividend = dividend_policy.value or 0.0
            elif dividend_policy.policy == "payout_ratio":
                dividend = max(0.0, ni * (dividend_policy.value or 0.0))
        is_list.append({
            "period_index": t,
            "revenue": rev_t,
            "cogs": cogs_t,
            "gross_profit": gross,
            "operating_expenses": fixed_opex[t],
            "ebitda": ebitda,
            "depreciation_amortization": da_per_month[t],
            "ebit": ebit,
            "interest_expense": interest[t],
            "ebt": ebt,
            "nol_offset": nol_used,
            "taxable_income": taxable_income,
            "tax": tax,
            "net_income": ni,
            "nol_balance": nol_balance,
            "dividends": dividend,
        })
    return is_list


def _accumulate_re(
    horizon: int,
    initial_equity: float,
    is_list: list[dict[str, Any]],
    equity_raises_per_period: list[float],
) -> list[float]:
    """Retained earnings series (length horizon+1; index 0 = opening balance)."""
    re = [initial_equity]
    for t in range(horizon):
        re.append(
            re[-1]
            + is_list[t]["net_income"]
            - is_list[t].get("dividends", 0.0)
            + equity_raises_per_period[t]
        )
    return re


def _build_balance_sheet(
    horizon: int,
    ar: list[float],
    ap: list[float],
    inv: list[float],
    ppe_gross: list[float],
    acc_depr: list[float],
    debt_result: Any,
    re_series: list[float],
    cumul_waterfall_debt: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Build per-period balance sheet. Cash is the balancing plug. # IAS 1"""
    wf_debt = cumul_waterfall_debt or [0.0] * horizon
    bs_list: list[dict[str, Any]] = []
    for t in range(horizon):
        current_assets_ex_cash = ar[t] + inv[t]
        ppe_net = ppe_gross[t] - acc_depr[t]
        total_assets_ex_cash = current_assets_ex_cash + ppe_net
        total_liab = (
            ap[t]
            + debt_result.current_debt_per_period[t]
            + debt_result.non_current_debt_per_period[t]
            + wf_debt[t]
        )
        total_equity = re_series[t + 1]
        cash_plug = total_liab + total_equity - total_assets_ex_cash
        bs_list.append({
            "period_index": t,
            "cash": cash_plug,
            "accounts_receivable": ar[t],
            "inventory": inv[t],
            "total_current_assets": cash_plug + ar[t] + inv[t],
            "ppe_gross": ppe_gross[t],
            "accumulated_depreciation": acc_depr[t],
            "ppe_net": ppe_net,
            "total_assets": total_assets_ex_cash + cash_plug,
            "accounts_payable": ap[t],
            "debt_current": debt_result.current_debt_per_period[t],
            "debt_non_current": debt_result.non_current_debt_per_period[t],
            "total_current_liabilities": ap[t] + debt_result.current_debt_per_period[t],
            "total_liabilities": total_liab,
            "total_equity": total_equity,
            "total_liabilities_equity": total_liab + total_equity,
        })
    return bs_list


def _build_cash_flow(
    horizon: int,
    initial_cash: float,
    is_list: list[dict[str, Any]],
    bs_list: list[dict[str, Any]],
    da_per_month: list[float],
    ar: list[float],
    inv: list[float],
    ap: list[float],
    ppe_gross: list[float],
    debt_result: Any,
    equity_raises_per_period: list[float],
) -> list[dict[str, Any]]:
    """Build per-period cash flow statement. Closing cash must reconcile with BS. # IAS 7"""
    opening_cash = [initial_cash] + [bs_list[t]["cash"] for t in range(horizon - 1)]
    cf_list: list[dict[str, Any]] = []
    for t in range(horizon):
        ni_t = is_list[t]["net_income"]
        da_t = da_per_month[t]
        delta_ar = ar[t] - (ar[t - 1] if t > 0 else 0)
        delta_inv = inv[t] - (inv[t - 1] if t > 0 else 0)
        delta_ap = ap[t] - (ap[t - 1] if t > 0 else 0)
        operating = ni_t + da_t - delta_ar - delta_inv + delta_ap
        investing = -(ppe_gross[t] - (ppe_gross[t - 1] if t > 0 else 0))
        debt_draws = debt_result.draws_per_period[t]
        debt_repayments = debt_result.repayments_per_period[t]
        closing = bs_list[t]["cash"]
        financing = closing - opening_cash[t] - operating - investing
        net_cf = operating + investing + financing
        cf_list.append({
            "period_index": t,
            "operating": operating,
            "investing": investing,
            "debt_draws": debt_draws,
            "debt_repayments": debt_repayments,
            "dividends_paid": is_list[t].get("dividends", 0.0),
            "equity_raised": equity_raises_per_period[t],
            "financing": financing,
            "net_cf": net_cf,
            "opening_cash": opening_cash[t],
            "closing_cash": closing,
        })
        if abs(closing - (opening_cash[t] + net_cf)) > 0.01:
            raise StatementImbalanceError(
                f"CF closing cash {closing} != BS cash {bs_list[t]['cash']} at period {t}",
                details={"period": t, "cf_closing": closing, "bs_cash": bs_list[t]["cash"]},
            )
    return cf_list


def _apply_waterfall_loop(
    *,
    horizon: int,
    tax_rate: float,
    nol_enabled: bool,
    initial_equity: float,
    initial_cash: float,
    ar: list[float],
    inv: list[float],
    ap: list[float],
    ppe_gross: list[float],
    acc_depr: list[float],
    debt_result: Any,
    equity_raises_per_period: list[float],
    plug_facilities: list[Any],
    minimum_cash: float,
    dividend_policy: Any | None,
    is_list: list[dict[str, Any]],
    bs_list: list[dict[str, Any]],
    cf_list: list[dict[str, Any]],
) -> None:
    """Iteratively apply funding waterfall to cover cash shortfalls (up to 5 passes).

    Modifies is_list, bs_list, and cf_list in-place to reflect waterfall draws/interest.
    """
    original_interest = [is_list[t]["interest_expense"] for t in range(horizon)]
    cumul_waterfall_debt = [0.0] * horizon
    cumul_waterfall_interest = [0.0] * horizon
    total_assets_ex_cash_per_t = [
        ar[t] + inv[t] + (ppe_gross[t] - acc_depr[t]) for t in range(horizon)
    ]

    for _ in range(5):
        closing_cash = [bs_list[t]["cash"] for t in range(horizon)]
        asset_values = {
            "ar": [bs_list[t]["accounts_receivable"] for t in range(horizon)],
            "inventory": [bs_list[t]["inventory"] for t in range(horizon)],
        }
        waterfall = apply_funding_waterfall(
            closing_cash, plug_facilities, minimum_cash, horizon, asset_values
        )
        any_injection = any(
            waterfall.additional_draws.get(f.facility_id, [0.0] * horizon)[t] > 0
            for f in plug_facilities
            for t in range(horizon)
        )
        any_waterfall_interest = any(v > 0 for v in waterfall.waterfall_interest)
        if not any_injection and not any_waterfall_interest:
            break

        for t in range(horizon):
            cumul_waterfall_debt[t] += waterfall.waterfall_debt_per_period[t]
            cumul_waterfall_interest[t] += waterfall.waterfall_interest[t]

        # Recompute IS with updated interest and NOL carry-forward (REM-08)
        wf_nol_balance = 0.0
        for t in range(horizon):
            is_list[t]["interest_expense"] = original_interest[t] + cumul_waterfall_interest[t]
            ebt_t = is_list[t]["ebit"] - is_list[t]["interest_expense"]
            is_list[t]["ebt"] = ebt_t
            wf_nol_used = 0.0
            if nol_enabled and ebt_t > 0 and wf_nol_balance > 0:
                wf_nol_used = min(wf_nol_balance, ebt_t)
                wf_nol_balance -= wf_nol_used
            wf_taxable = max(0.0, ebt_t - wf_nol_used)
            is_list[t]["nol_offset"] = wf_nol_used
            is_list[t]["taxable_income"] = wf_taxable
            is_list[t]["tax"] = wf_taxable * tax_rate
            if nol_enabled and ebt_t < 0:
                wf_nol_balance += abs(ebt_t)
            is_list[t]["nol_balance"] = wf_nol_balance
            is_list[t]["net_income"] = ebt_t - is_list[t]["tax"]
            if dividend_policy and dividend_policy.policy == "payout_ratio":
                is_list[t]["dividends"] = max(
                    0.0, is_list[t]["net_income"] * (dividend_policy.value or 0.0)
                )

        # Recompute RE, BS, and CF with updated IS + cumulative waterfall debt
        re = _accumulate_re(horizon, initial_equity, is_list, equity_raises_per_period)
        for t in range(horizon):
            total_liab = (
                ap[t]
                + debt_result.current_debt_per_period[t]
                + debt_result.non_current_debt_per_period[t]
                + cumul_waterfall_debt[t]
            )
            total_equity = re[t + 1]
            cash_plug = total_liab + total_equity - total_assets_ex_cash_per_t[t]
            bs_list[t]["cash"] = cash_plug
            bs_list[t]["total_liabilities"] = total_liab
            bs_list[t]["total_equity"] = total_equity
            bs_list[t]["total_assets"] = total_assets_ex_cash_per_t[t] + cash_plug
            bs_list[t]["total_current_assets"] = cash_plug + ar[t] + inv[t]
            bs_list[t]["total_liabilities_equity"] = total_liab + total_equity

        opening_cash = [initial_cash] + [bs_list[t]["cash"] for t in range(horizon - 1)]
        for t in range(horizon):
            ni_t = is_list[t]["net_income"]
            da_t = is_list[t]["depreciation_amortization"]
            delta_ar = ar[t] - (ar[t - 1] if t > 0 else 0)
            delta_inv = inv[t] - (inv[t - 1] if t > 0 else 0)
            delta_ap = ap[t] - (ap[t - 1] if t > 0 else 0)
            operating = ni_t + da_t - delta_ar - delta_inv + delta_ap
            investing = -(ppe_gross[t] - (ppe_gross[t - 1] if t > 0 else 0))
            closing = bs_list[t]["cash"]
            financing = closing - opening_cash[t] - operating - investing
            cf_list[t]["operating"] = operating
            cf_list[t]["financing"] = financing
            cf_list[t]["closing_cash"] = closing
            cf_list[t]["opening_cash"] = opening_cash[t]
            cf_list[t]["net_cf"] = operating + investing + financing


def generate_statements(config: ModelConfig, time_series: dict[str, list[float]]) -> Statements:
    """
    Produce Income Statement, Balance Sheet, Cash Flow from engine time_series.
    BS balances via cash plug; CF closing cash = BS cash.
    """
    horizon = config.metadata.horizon_months
    tax_rate = config.metadata.tax_rate or 0.0
    initial_cash = config.metadata.initial_cash or 0.0
    initial_equity = config.metadata.initial_equity or 0.0
    nol_enabled = getattr(config.metadata, "nol_carry_forward", True)

    nodes = [
        n.model_dump() if hasattr(n, "model_dump") else n for n in config.driver_blueprint.nodes
    ]
    revenue, cogs = _revenue_and_cogs_from_timeseries(time_series, nodes, horizon)

    revenue_by_segment: dict[str, list[float]] = {}
    for rs in config.assumptions.revenue_streams:
        seg = getattr(rs, "business_line", None) or "default"
        if seg not in revenue_by_segment:
            revenue_by_segment[seg] = [0.0] * horizon
        stream_driver_refs = {d.ref for d in rs.drivers.volume + rs.drivers.pricing}
        for node in nodes:
            if node.get("type") != "output":
                continue
            nid = node["node_id"]
            if nid not in time_series:
                continue
            classification = (node.get("classification") or "").lower()
            if not classification:
                label = (node.get("label") or "").lower()
                nid_lower = nid.lower()
                if any(k in label for k in _REVENUE_KEYWORDS) or any(k in nid_lower for k in _REVENUE_KEYWORDS):
                    classification = "revenue"
            if classification == "revenue":
                formula = next(
                    (f for f in config.driver_blueprint.formulas if f.output_node_id == nid),
                    None,
                )
                if formula and stream_driver_refs & set(formula.inputs):
                    for t in range(horizon):
                        revenue_by_segment[seg][t] += time_series[nid][t]

    fixed_opex = _fixed_opex_per_period(config, horizon)
    wc_days = _ar_ap_inv_days_per_period(config, horizon)
    da_per_month = _compute_da_per_period(config, horizon)

    # Debt schedule (interest, draws, repayments, current/non-current)
    debt_result = empty_debt_result(horizon)
    if config.assumptions.funding and config.assumptions.funding.debt_facilities:
        non_plug = [f for f in config.assumptions.funding.debt_facilities if not f.is_cash_plug]
        if non_plug:
            debt_result = calculate_debt_schedule(non_plug, horizon)

    equity_raises_per_period = _compute_equity_raises_per_period(config, horizon, debt_result)

    # Income statement
    is_list = _build_income_statement(
        horizon, tax_rate, nol_enabled, revenue, cogs, fixed_opex,
        da_per_month, debt_result.interest_per_period, config,
    )

    # Working capital arrays for BS and CF
    ar_days, ap_days, inv_days = (
        zip(*wc_days) if wc_days else ([0] * horizon, [0] * horizon, [0] * horizon)
    )
    days_per_period = 30.0 if getattr(config.metadata, "resolution", "monthly") == "monthly" else 365.0
    rev_per_day = [revenue[t] / days_per_period for t in range(horizon)]
    cogs_per_day = [cogs[t] / days_per_period for t in range(horizon)]

    ar = [rev_per_day[t] * ar_days[t] for t in range(horizon)]
    ap = [cogs_per_day[t] * ap_days[t] for t in range(horizon)]
    inv = [cogs_per_day[t] * inv_days[t] for t in range(horizon)]

    # PP&E: cumulative capex gross and accumulated depreciation
    ppe_gross: list[float] = [0.0] * horizon
    if config.assumptions.capex and config.assumptions.capex.items:
        for item in config.assumptions.capex.items:
            if item.month < horizon:
                ppe_gross[item.month] += item.amount
    for t in range(1, horizon):
        ppe_gross[t] += ppe_gross[t - 1]

    acc_depr = [0.0] * horizon
    for t in range(horizon):
        acc_depr[t] = acc_depr[t - 1] + da_per_month[t] if t > 0 else da_per_month[0]

    # Balance sheet (cash as plug) and cash flow
    re_series = _accumulate_re(horizon, initial_equity, is_list, equity_raises_per_period)
    bs_list = _build_balance_sheet(horizon, ar, ap, inv, ppe_gross, acc_depr, debt_result, re_series)
    cf_list = _build_cash_flow(
        horizon, initial_cash, is_list, bs_list, da_per_month,
        ar, inv, ap, ppe_gross, debt_result, equity_raises_per_period,
    )

    # Funding waterfall: cover shortfalls with cash-plug facilities, then recalc
    minimum_cash = getattr(config.assumptions.working_capital, "minimum_cash", 0.0) or 0.0
    plug_facilities: list[Any] = []
    if config.assumptions.funding and config.assumptions.funding.debt_facilities:
        plug_facilities = [f for f in config.assumptions.funding.debt_facilities if f.is_cash_plug]

    if plug_facilities and minimum_cash > 0:
        dividend_policy = (
            config.assumptions.funding.dividends
            if config.assumptions.funding and config.assumptions.funding.dividends
            else None
        )
        _apply_waterfall_loop(
            horizon=horizon,
            tax_rate=tax_rate,
            nol_enabled=nol_enabled,
            initial_equity=initial_equity,
            initial_cash=initial_cash,
            ar=ar,
            inv=inv,
            ap=ap,
            ppe_gross=ppe_gross,
            acc_depr=acc_depr,
            debt_result=debt_result,
            equity_raises_per_period=equity_raises_per_period,
            plug_facilities=plug_facilities,
            minimum_cash=minimum_cash,
            dividend_policy=dividend_policy,
            is_list=is_list,
            bs_list=bs_list,
            cf_list=cf_list,
        )

    periods = [f"P{t}" for t in range(horizon)]
    return Statements(
        income_statement=is_list,
        balance_sheet=bs_list,
        cash_flow=cf_list,
        periods=periods,
        revenue_by_segment=revenue_by_segment,
    )
