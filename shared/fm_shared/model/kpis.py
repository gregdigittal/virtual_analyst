"""
KPI calculator from statements.
"""

from __future__ import annotations

from typing import Any

from shared.fm_shared.model.statements import Statements


def calculate_kpis(statements: Statements) -> list[dict[str, Any]]:
    """Compute gross margin %, EBITDA margin %, net margin %, growth, ratios, FCF, CCC."""
    is_list = statements.income_statement
    bs_list = statements.balance_sheet
    cf_list = statements.cash_flow
    n = len(is_list)
    kpis: list[dict[str, Any]] = []

    for t in range(n):
        rev = is_list[t]["revenue"]
        gross = is_list[t]["gross_profit"]
        ebitda = is_list[t]["ebitda"]
        ni = is_list[t]["net_income"]

        gross_margin_pct = (gross / rev * 100) if rev else 0.0
        ebitda_margin_pct = (ebitda / rev * 100) if rev else 0.0
        net_margin_pct = (ni / rev * 100) if rev else 0.0

        rev_prev = is_list[t - 1]["revenue"] if t > 0 else rev
        revenue_growth_pct: float | None = (
            None if t == 0 else (((rev - rev_prev) / rev_prev * 100) if rev_prev else 0.0)
        )

        ca = bs_list[t]["total_current_assets"]
        # Use current liabilities (e.g. total_current_liabilities or accounts_payable), not total_liabilities
        cl_current = bs_list[t].get("total_current_liabilities") or bs_list[t].get("accounts_payable") or 0.0
        current_ratio = (ca / cl_current) if cl_current else 0.0

        debt_current = bs_list[t].get("debt_current", 0.0)
        debt_non_current = bs_list[t].get("debt_non_current", 0.0)
        total_debt = debt_current + debt_non_current
        total_equity = bs_list[t]["total_equity"]
        debt_equity = (total_debt / total_equity) if (total_equity and total_debt) else None

        interest = is_list[t]["interest_expense"]
        principal = cf_list[t].get("debt_repayments", 0.0)
        debt_service = interest + principal
        dscr = (ebitda / debt_service) if debt_service else None

        roe = (ni / total_equity * 100) if total_equity else 0.0

        operating_cf = cf_list[t]["operating"]
        investing_cf = cf_list[t]["investing"]
        fcf = operating_cf + investing_cf

        rev_daily = rev / 30.0 if rev else 0.0
        cogs_t = is_list[t]["cogs"]
        cogs_daily = cogs_t / 30.0 if cogs_t else 0.0
        ar_val = bs_list[t]["accounts_receivable"]
        inv_val = bs_list[t]["inventory"]
        ap_val = bs_list[t]["accounts_payable"]
        dso = (ar_val / rev_daily) if rev_daily else 0.0
        dio = (inv_val / cogs_daily) if cogs_daily else 0.0
        dpo = (ap_val / cogs_daily) if cogs_daily else 0.0
        ccc = dso + dio - dpo

        kpis.append(
            {
                "period_index": t,
                "gross_margin_pct": round(gross_margin_pct, 2),
                "ebitda_margin_pct": round(ebitda_margin_pct, 2),
                "net_margin_pct": round(net_margin_pct, 2),
                "revenue_growth_pct": round(revenue_growth_pct, 2) if revenue_growth_pct is not None else None,
                "current_ratio": round(current_ratio, 2),
                "debt_equity": round(debt_equity, 2) if debt_equity is not None else None,
                "dscr": round(dscr, 2) if dscr is not None else None,
                "roe": round(roe, 2),
                "fcf": round(fcf, 2),
                "cash_conversion_cycle": round(ccc, 2),
            }
        )
    return kpis
