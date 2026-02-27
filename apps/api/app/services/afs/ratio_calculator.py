"""AFS Ratio Calculator — computes financial ratios from trial balance data."""

from __future__ import annotations

import re
from typing import Any

# Account classification patterns (key = category, value = list of regex patterns)
ACCOUNT_PATTERNS: dict[str, list[str]] = {
    "revenue": [r"revenue", r"sales", r"turnover", r"income from operations"],
    "cogs": [r"cost of sales", r"cost of goods", r"cogs", r"cost of revenue"],
    "operating_expense": [r"operating exp", r"admin", r"selling", r"distribution", r"marketing", r"depreciation", r"amortis"],
    "interest_expense": [r"interest exp", r"finance cost", r"borrowing cost"],
    "tax_expense": [r"income tax", r"tax expense", r"taxation"],
    "accounts_receivable": [r"accounts? receivable", r"trade receivable", r"trade debtor"],
    "inventory": [r"inventor", r"stock", r"raw material", r"finished goods", r"work.in.progress"],
    "accounts_payable": [r"accounts? payable", r"trade payable", r"trade creditor"],
    "cash": [r"cash", r"bank"],
    "current_assets_other": [r"prepaid", r"other current asset"],
    "non_current_assets": [r"property", r"plant", r"equipment", r"ppe", r"intangible", r"goodwill", r"investment property", r"right.of.use"],
    "current_liabilities_other": [r"accrued", r"current portion", r"short.term loan", r"overdraft", r"vat payable", r"other current liab"],
    "non_current_liabilities": [r"long.term loan", r"mortgage", r"bond payable", r"lease liab", r"deferred tax liab"],
    "equity": [r"share capital", r"retained earn", r"reserves?$", r"equity", r"accumulated profit", r"accumulated loss"],
}


def classify_accounts(accounts: list[dict[str, Any]]) -> dict[str, float]:
    """Classify TB accounts into financial categories and sum their net values."""
    totals: dict[str, float] = {}
    for acct in accounts:
        name = (acct.get("account_name") or "").lower()
        net = float(acct.get("net", 0) or 0)
        matched = False
        for category, patterns in ACCOUNT_PATTERNS.items():
            if any(re.search(p, name) for p in patterns):
                totals[category] = totals.get(category, 0) + net
                matched = True
                break
        if not matched:
            totals.setdefault("unclassified", 0)
            totals["unclassified"] = totals.get("unclassified", 0) + net
    return totals


def compute_ratios(classified: dict[str, float]) -> dict[str, float | None]:
    """Compute 16 financial ratios from classified account totals."""
    revenue = abs(classified.get("revenue", 0))
    cogs = abs(classified.get("cogs", 0))
    opex = abs(classified.get("operating_expense", 0))
    interest = abs(classified.get("interest_expense", 0))
    tax = abs(classified.get("tax_expense", 0))

    gross_profit = revenue - cogs
    operating_income = gross_profit - opex
    net_income = operating_income - interest - tax

    ar = abs(classified.get("accounts_receivable", 0))
    inv = abs(classified.get("inventory", 0))
    ap = abs(classified.get("accounts_payable", 0))
    cash = abs(classified.get("cash", 0))
    ca_other = abs(classified.get("current_assets_other", 0))

    current_assets = cash + ar + inv + ca_other
    nca = abs(classified.get("non_current_assets", 0))
    total_assets = current_assets + nca

    cl_other = abs(classified.get("current_liabilities_other", 0))
    current_liabilities = ap + cl_other
    ncl = abs(classified.get("non_current_liabilities", 0))
    total_liabilities = current_liabilities + ncl
    equity = abs(classified.get("equity", 0))

    def safe_div(num: float, den: float) -> float | None:
        return round(num / den, 4) if den else None

    # Efficiency intermediate values
    recv_days = safe_div(ar, revenue / 365) if revenue else None
    inv_days = safe_div(inv, cogs / 365) if cogs else None
    pay_days = safe_div(ap, cogs / 365) if cogs else None
    ccc = None
    if recv_days is not None and inv_days is not None and pay_days is not None:
        ccc = round(recv_days + inv_days - pay_days, 2)

    # Altman Z-score proxy: 1.2*WC/TA + 1.4*RE/TA + 3.3*EBIT/TA + 0.6*E/TL + 1.0*Rev/TA
    retained = classified.get("equity", 0)  # proxy
    z_proxy = None
    if total_assets:
        wc_ta = (current_assets - current_liabilities) / total_assets
        re_ta = retained / total_assets
        ebit_ta = operating_income / total_assets
        eq_tl = (equity / total_liabilities) if total_liabilities else 0
        rev_ta = revenue / total_assets
        z_proxy = round(1.2 * wc_ta + 1.4 * re_ta + 3.3 * ebit_ta + 0.6 * eq_tl + 1.0 * rev_ta, 4)

    return {
        "current_ratio": safe_div(current_assets, current_liabilities),
        "quick_ratio": safe_div(current_assets - inv, current_liabilities),
        "debt_to_equity": safe_div(total_liabilities, equity),
        "interest_coverage": safe_div(operating_income, interest),
        "debt_ratio": safe_div(total_liabilities, total_assets),
        "gross_margin_pct": safe_div(gross_profit * 100, revenue),
        "operating_margin_pct": safe_div(operating_income * 100, revenue),
        "net_margin_pct": safe_div(net_income * 100, revenue),
        "return_on_equity": safe_div(net_income * 100, equity),
        "return_on_assets": safe_div(net_income * 100, total_assets),
        "asset_turnover": safe_div(revenue, total_assets),
        "receivable_days": recv_days,
        "inventory_days": inv_days,
        "payable_days": pay_days,
        "cash_conversion_cycle": ccc,
        "altman_z_proxy": z_proxy,
        # Store derived totals for reference
        "_revenue": revenue,
        "_gross_profit": gross_profit,
        "_operating_income": operating_income,
        "_net_income": net_income,
        "_total_assets": total_assets,
        "_total_liabilities": total_liabilities,
        "_equity": equity,
        "_current_assets": current_assets,
        "_current_liabilities": current_liabilities,
    }


def compute_from_tb(data_json: list[dict[str, Any]]) -> dict[str, float | None]:
    """Full pipeline: classify TB accounts then compute ratios."""
    classified = classify_accounts(data_json)
    return compute_ratios(classified)
