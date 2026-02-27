# AFS Phase 5 — Analytics & Industry Benchmarking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add financial ratio analysis, trend comparison, industry benchmarking, AI anomaly detection, management commentary suggestions, and going concern assessment to the AFS module.

**Architecture:** A new `afs_analytics` table stores computed ratio snapshots per engagement. A pure-Python ratio calculator computes 16 financial ratios from trial balance account data. A seed JSON file provides industry benchmark percentiles. An AI service (via the existing LLMRouter) generates anomaly insights, management commentary, and going concern assessments. Five new endpoints expose the analytics, and a new frontend page displays ratios, sparkline trends, benchmark comparisons, and AI insights.

**Tech Stack:** Python/FastAPI, asyncpg, LLMRouter (Anthropic Claude / OpenAI GPT-4o), Next.js 14, TypeScript, Tailwind CSS

---

## Existing Infrastructure

### Trial Balance Data
- `afs_trial_balances` table stores `data_json` (array of `{account_name, debit, credit, net}`) per engagement
- Multiple TBs possible per engagement (different periods, entities)
- Parsed via `apps/api/app/services/afs/tb_parser.py`

### KPI Module (reference — not directly usable)
- `shared/fm_shared/model/kpis.py` computes KPIs from `Statements` dataclass (income_statement, balance_sheet, cash_flow lists)
- AFS trial balances are raw account-level data, not structured statements — need a different approach
- Pattern is useful as reference for ratio formulas

### LLM Service Pattern
- `LLMRouter` from `apps/api/app/services/llm/router.py` — task-label routing, provider fallback, structured JSON output
- Injected via `Depends(get_llm_router)` in endpoint functions
- Schema-validated responses via `response_schema` parameter
- Existing task labels: `afs_disclosure_draft`, `afs_tax_note`, etc.
- Import: `from apps.api.app.services.llm.provider import LLMResponse, Message`
- Import: `from apps.api.app.services.llm.router import LLMRouter`

### Benchmark Infrastructure
- `benchmark_aggregates` table (migration 0040): `segment_key`, `metric_name`, `median_value`, `p25_value`, `p75_value`, `sample_count`
- `tenant_benchmark_opt_in` table: tracks industry/size segment per tenant
- Router: `apps/api/app/routers/benchmark.py`

### AFS Router Patterns
- Composite PKs: `(tenant_id, entity_id)`
- RLS: `current_setting('app.tenant_id', true)` with 4 policies per table
- ID prefix pattern: `def _analytics_id() -> str: return f"aan_{uuid.uuid4().hex[:14]}"`
- Endpoint dependency: `llm: LLMRouter = Depends(get_llm_router)`

### Key Account Classification
Trial balance accounts need to be classified into financial statement categories for ratio computation. The approach: use account name pattern matching (regex) to map TB accounts into categories like revenue, COGS, current assets, etc.

---

## Task 1: Migration 0056 — AFS Analytics Table

**Files:**
- Create: `apps/api/app/db/migrations/0056_afs_analytics.sql`

```sql
-- 0056_afs_analytics.sql — AFS Phase 5: analytics snapshots

create table if not exists afs_analytics (
  tenant_id text not null references tenants(id) on delete cascade,
  analytics_id text not null,
  engagement_id text not null,
  computed_at timestamptz not null default now(),
  ratios_json jsonb not null default '{}'::jsonb,
  trends_json jsonb not null default '[]'::jsonb,
  benchmark_comparison_json jsonb not null default '{}'::jsonb,
  anomalies_json jsonb not null default '[]'::jsonb,
  commentary_json jsonb,
  going_concern_json jsonb,
  industry_segment text,
  status text not null check (status in ('computed','stale','error')) default 'computed',
  error_message text,
  computed_by text references users(id) on delete set null,
  primary key (tenant_id, analytics_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_analytics_engagement on afs_analytics(tenant_id, engagement_id);

-- RLS
alter table afs_analytics enable row level security;
drop policy if exists "afs_analytics_select" on afs_analytics;
drop policy if exists "afs_analytics_insert" on afs_analytics;
drop policy if exists "afs_analytics_update" on afs_analytics;
drop policy if exists "afs_analytics_delete" on afs_analytics;
create policy "afs_analytics_select" on afs_analytics for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_analytics_insert" on afs_analytics for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_analytics_update" on afs_analytics for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_analytics_delete" on afs_analytics for delete using (tenant_id = current_setting('app.tenant_id', true));
```

**Verification:** `python -c "import apps.api.app.routers.afs"` — should import fine (SQL only).

---

## Task 2: Ratio Calculator Service

**Files:**
- Create: `apps/api/app/services/afs/ratio_calculator.py`

This service:
1. Takes raw trial balance `data_json` (list of `{account_name, debit, credit, net}`)
2. Classifies accounts into financial statement categories via regex pattern matching
3. Computes 16 financial ratios
4. Returns a structured dict of ratio results

### Account Classification

Map account names to categories using keyword matching:

| Category | Keywords (case-insensitive) |
|----------|---------------------------|
| `revenue` | revenue, sales, turnover, income from operations |
| `cogs` | cost of sales, cost of goods, cogs, cost of revenue |
| `operating_expense` | operating expense, admin, selling, distribution, marketing, depreciation, amortisation |
| `interest_expense` | interest expense, finance cost, borrowing cost |
| `tax_expense` | income tax, tax expense, taxation |
| `current_assets` | cash, bank, accounts receivable, trade receivable, inventory, stock, prepaid, other current asset |
| `non_current_assets` | property, plant, equipment, ppe, intangible, goodwill, investment property, right-of-use |
| `current_liabilities` | accounts payable, trade payable, accrued, current portion, short-term loan, overdraft, vat payable, tax payable, other current liab |
| `non_current_liabilities` | long-term loan, mortgage, bond payable, lease liability, non-current, deferred tax liability |
| `equity` | share capital, retained earnings, reserves, equity, accumulated profit, accumulated loss |
| `accounts_receivable` | accounts receivable, trade receivable, trade debtor |
| `inventory` | inventory, stock, raw material, finished goods, work in progress |
| `accounts_payable` | accounts payable, trade payable, trade creditor |

### Ratios to Compute

```python
RATIO_DEFINITIONS = {
    # Liquidity
    "current_ratio": {"formula": "current_assets / current_liabilities", "category": "liquidity"},
    "quick_ratio": {"formula": "(current_assets - inventory) / current_liabilities", "category": "liquidity"},

    # Solvency
    "debt_to_equity": {"formula": "total_liabilities / equity", "category": "solvency"},
    "interest_coverage": {"formula": "operating_income / interest_expense", "category": "solvency"},
    "debt_ratio": {"formula": "total_liabilities / total_assets", "category": "solvency"},

    # Profitability
    "gross_margin_pct": {"formula": "gross_profit / revenue * 100", "category": "profitability"},
    "operating_margin_pct": {"formula": "operating_income / revenue * 100", "category": "profitability"},
    "net_margin_pct": {"formula": "net_income / revenue * 100", "category": "profitability"},
    "return_on_equity": {"formula": "net_income / equity * 100", "category": "profitability"},
    "return_on_assets": {"formula": "net_income / total_assets * 100", "category": "profitability"},

    # Efficiency
    "asset_turnover": {"formula": "revenue / total_assets", "category": "efficiency"},
    "receivable_days": {"formula": "accounts_receivable / revenue * 365", "category": "efficiency"},
    "inventory_days": {"formula": "inventory / cogs * 365", "category": "efficiency"},
    "payable_days": {"formula": "accounts_payable / cogs * 365", "category": "efficiency"},
    "cash_conversion_cycle": {"formula": "receivable_days + inventory_days - payable_days", "category": "efficiency"},

    # Going concern
    "altman_z_proxy": {"formula": "simplified proxy using working capital, retained earnings, EBIT, equity, revenue, assets", "category": "going_concern"},
}
```

### Implementation

```python
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
```

**Verification:** `python -c "from apps.api.app.services.afs.ratio_calculator import compute_from_tb; print('OK')"`

---

## Task 3: Industry Benchmark Seed Data

**Files:**
- Create: `apps/api/app/data/industry_benchmarks.json`

This JSON file contains benchmark percentiles (p25, median, p75) for 16 ratios across 8 industry segments. These are illustrative defaults — in production they'd be computed from aggregated opt-in data.

```json
{
  "_description": "Industry benchmark percentiles for AFS analytics. Segments match tenant_benchmark_opt_in.industry_segment.",
  "segments": {
    "general": {
      "current_ratio": {"p25": 1.0, "median": 1.5, "p75": 2.2},
      "quick_ratio": {"p25": 0.6, "median": 1.0, "p75": 1.5},
      "debt_to_equity": {"p25": 0.3, "median": 0.8, "p75": 1.5},
      "interest_coverage": {"p25": 2.0, "median": 4.0, "p75": 8.0},
      "debt_ratio": {"p25": 0.25, "median": 0.45, "p75": 0.65},
      "gross_margin_pct": {"p25": 25.0, "median": 35.0, "p75": 50.0},
      "operating_margin_pct": {"p25": 5.0, "median": 12.0, "p75": 20.0},
      "net_margin_pct": {"p25": 3.0, "median": 8.0, "p75": 15.0},
      "return_on_equity": {"p25": 5.0, "median": 12.0, "p75": 22.0},
      "return_on_assets": {"p25": 3.0, "median": 7.0, "p75": 14.0},
      "asset_turnover": {"p25": 0.4, "median": 0.8, "p75": 1.4},
      "receivable_days": {"p25": 25, "median": 45, "p75": 70},
      "inventory_days": {"p25": 20, "median": 45, "p75": 80},
      "payable_days": {"p25": 20, "median": 40, "p75": 65},
      "cash_conversion_cycle": {"p25": 10, "median": 50, "p75": 90},
      "altman_z_proxy": {"p25": 1.5, "median": 2.5, "p75": 4.0}
    },
    "manufacturing": {
      "current_ratio": {"p25": 1.2, "median": 1.8, "p75": 2.5},
      "quick_ratio": {"p25": 0.5, "median": 0.9, "p75": 1.3},
      "debt_to_equity": {"p25": 0.4, "median": 1.0, "p75": 1.8},
      "interest_coverage": {"p25": 2.5, "median": 5.0, "p75": 9.0},
      "debt_ratio": {"p25": 0.3, "median": 0.5, "p75": 0.65},
      "gross_margin_pct": {"p25": 20.0, "median": 30.0, "p75": 40.0},
      "operating_margin_pct": {"p25": 4.0, "median": 10.0, "p75": 16.0},
      "net_margin_pct": {"p25": 2.0, "median": 6.0, "p75": 12.0},
      "return_on_equity": {"p25": 6.0, "median": 14.0, "p75": 22.0},
      "return_on_assets": {"p25": 3.0, "median": 6.0, "p75": 12.0},
      "asset_turnover": {"p25": 0.6, "median": 1.0, "p75": 1.5},
      "receivable_days": {"p25": 30, "median": 50, "p75": 75},
      "inventory_days": {"p25": 40, "median": 70, "p75": 110},
      "payable_days": {"p25": 25, "median": 45, "p75": 70},
      "cash_conversion_cycle": {"p25": 30, "median": 70, "p75": 120},
      "altman_z_proxy": {"p25": 1.3, "median": 2.2, "p75": 3.5}
    },
    "retail": {
      "current_ratio": {"p25": 0.9, "median": 1.3, "p75": 1.8},
      "quick_ratio": {"p25": 0.3, "median": 0.5, "p75": 0.9},
      "debt_to_equity": {"p25": 0.5, "median": 1.2, "p75": 2.0},
      "interest_coverage": {"p25": 2.0, "median": 4.5, "p75": 8.0},
      "debt_ratio": {"p25": 0.3, "median": 0.55, "p75": 0.7},
      "gross_margin_pct": {"p25": 25.0, "median": 35.0, "p75": 45.0},
      "operating_margin_pct": {"p25": 3.0, "median": 7.0, "p75": 12.0},
      "net_margin_pct": {"p25": 1.5, "median": 4.0, "p75": 8.0},
      "return_on_equity": {"p25": 8.0, "median": 16.0, "p75": 28.0},
      "return_on_assets": {"p25": 3.0, "median": 6.0, "p75": 10.0},
      "asset_turnover": {"p25": 1.2, "median": 2.0, "p75": 3.0},
      "receivable_days": {"p25": 5, "median": 15, "p75": 30},
      "inventory_days": {"p25": 30, "median": 55, "p75": 90},
      "payable_days": {"p25": 20, "median": 40, "p75": 60},
      "cash_conversion_cycle": {"p25": 5, "median": 30, "p75": 65},
      "altman_z_proxy": {"p25": 1.4, "median": 2.4, "p75": 3.8}
    },
    "technology": {
      "current_ratio": {"p25": 1.5, "median": 2.5, "p75": 4.0},
      "quick_ratio": {"p25": 1.3, "median": 2.2, "p75": 3.5},
      "debt_to_equity": {"p25": 0.1, "median": 0.3, "p75": 0.7},
      "interest_coverage": {"p25": 5.0, "median": 12.0, "p75": 25.0},
      "debt_ratio": {"p25": 0.1, "median": 0.25, "p75": 0.45},
      "gross_margin_pct": {"p25": 50.0, "median": 65.0, "p75": 80.0},
      "operating_margin_pct": {"p25": 8.0, "median": 18.0, "p75": 30.0},
      "net_margin_pct": {"p25": 5.0, "median": 14.0, "p75": 25.0},
      "return_on_equity": {"p25": 8.0, "median": 18.0, "p75": 30.0},
      "return_on_assets": {"p25": 5.0, "median": 12.0, "p75": 22.0},
      "asset_turnover": {"p25": 0.3, "median": 0.6, "p75": 1.0},
      "receivable_days": {"p25": 30, "median": 50, "p75": 80},
      "inventory_days": {"p25": 5, "median": 15, "p75": 30},
      "payable_days": {"p25": 20, "median": 40, "p75": 60},
      "cash_conversion_cycle": {"p25": -10, "median": 20, "p75": 55},
      "altman_z_proxy": {"p25": 2.0, "median": 3.5, "p75": 6.0}
    },
    "financial_services": {
      "current_ratio": {"p25": 1.0, "median": 1.2, "p75": 1.5},
      "quick_ratio": {"p25": 0.8, "median": 1.0, "p75": 1.3},
      "debt_to_equity": {"p25": 2.0, "median": 5.0, "p75": 10.0},
      "interest_coverage": {"p25": 1.5, "median": 3.0, "p75": 5.0},
      "debt_ratio": {"p25": 0.6, "median": 0.8, "p75": 0.92},
      "gross_margin_pct": {"p25": 40.0, "median": 55.0, "p75": 70.0},
      "operating_margin_pct": {"p25": 15.0, "median": 28.0, "p75": 40.0},
      "net_margin_pct": {"p25": 10.0, "median": 22.0, "p75": 35.0},
      "return_on_equity": {"p25": 8.0, "median": 14.0, "p75": 20.0},
      "return_on_assets": {"p25": 0.5, "median": 1.2, "p75": 2.5},
      "asset_turnover": {"p25": 0.02, "median": 0.05, "p75": 0.1},
      "receivable_days": {"p25": 15, "median": 30, "p75": 50},
      "inventory_days": {"p25": 0, "median": 0, "p75": 5},
      "payable_days": {"p25": 15, "median": 30, "p75": 50},
      "cash_conversion_cycle": {"p25": -10, "median": 0, "p75": 15},
      "altman_z_proxy": {"p25": 0.8, "median": 1.5, "p75": 2.5}
    },
    "mining": {
      "current_ratio": {"p25": 1.0, "median": 1.5, "p75": 2.0},
      "quick_ratio": {"p25": 0.6, "median": 1.0, "p75": 1.5},
      "debt_to_equity": {"p25": 0.3, "median": 0.6, "p75": 1.2},
      "interest_coverage": {"p25": 2.0, "median": 5.0, "p75": 10.0},
      "debt_ratio": {"p25": 0.2, "median": 0.4, "p75": 0.55},
      "gross_margin_pct": {"p25": 20.0, "median": 35.0, "p75": 50.0},
      "operating_margin_pct": {"p25": 8.0, "median": 18.0, "p75": 30.0},
      "net_margin_pct": {"p25": 4.0, "median": 12.0, "p75": 22.0},
      "return_on_equity": {"p25": 5.0, "median": 12.0, "p75": 22.0},
      "return_on_assets": {"p25": 3.0, "median": 8.0, "p75": 15.0},
      "asset_turnover": {"p25": 0.3, "median": 0.5, "p75": 0.8},
      "receivable_days": {"p25": 20, "median": 40, "p75": 65},
      "inventory_days": {"p25": 30, "median": 55, "p75": 90},
      "payable_days": {"p25": 25, "median": 45, "p75": 70},
      "cash_conversion_cycle": {"p25": 15, "median": 50, "p75": 90},
      "altman_z_proxy": {"p25": 1.2, "median": 2.3, "p75": 4.0}
    },
    "construction": {
      "current_ratio": {"p25": 1.0, "median": 1.3, "p75": 1.8},
      "quick_ratio": {"p25": 0.7, "median": 1.0, "p75": 1.4},
      "debt_to_equity": {"p25": 0.5, "median": 1.2, "p75": 2.5},
      "interest_coverage": {"p25": 1.5, "median": 3.5, "p75": 7.0},
      "debt_ratio": {"p25": 0.35, "median": 0.55, "p75": 0.72},
      "gross_margin_pct": {"p25": 12.0, "median": 20.0, "p75": 30.0},
      "operating_margin_pct": {"p25": 3.0, "median": 7.0, "p75": 12.0},
      "net_margin_pct": {"p25": 1.5, "median": 4.0, "p75": 8.0},
      "return_on_equity": {"p25": 6.0, "median": 14.0, "p75": 24.0},
      "return_on_assets": {"p25": 2.0, "median": 5.0, "p75": 9.0},
      "asset_turnover": {"p25": 0.8, "median": 1.3, "p75": 2.0},
      "receivable_days": {"p25": 35, "median": 60, "p75": 95},
      "inventory_days": {"p25": 10, "median": 25, "p75": 50},
      "payable_days": {"p25": 30, "median": 55, "p75": 85},
      "cash_conversion_cycle": {"p25": 5, "median": 30, "p75": 70},
      "altman_z_proxy": {"p25": 1.0, "median": 2.0, "p75": 3.2}
    },
    "healthcare": {
      "current_ratio": {"p25": 1.2, "median": 1.8, "p75": 2.8},
      "quick_ratio": {"p25": 0.9, "median": 1.5, "p75": 2.3},
      "debt_to_equity": {"p25": 0.3, "median": 0.7, "p75": 1.3},
      "interest_coverage": {"p25": 3.0, "median": 6.0, "p75": 12.0},
      "debt_ratio": {"p25": 0.2, "median": 0.4, "p75": 0.6},
      "gross_margin_pct": {"p25": 35.0, "median": 50.0, "p75": 65.0},
      "operating_margin_pct": {"p25": 5.0, "median": 12.0, "p75": 20.0},
      "net_margin_pct": {"p25": 3.0, "median": 8.0, "p75": 16.0},
      "return_on_equity": {"p25": 6.0, "median": 14.0, "p75": 22.0},
      "return_on_assets": {"p25": 4.0, "median": 8.0, "p75": 14.0},
      "asset_turnover": {"p25": 0.4, "median": 0.7, "p75": 1.2},
      "receivable_days": {"p25": 30, "median": 50, "p75": 80},
      "inventory_days": {"p25": 15, "median": 30, "p75": 55},
      "payable_days": {"p25": 20, "median": 40, "p75": 60},
      "cash_conversion_cycle": {"p25": 15, "median": 40, "p75": 75},
      "altman_z_proxy": {"p25": 1.5, "median": 2.8, "p75": 4.5}
    }
  },
  "ratio_labels": {
    "current_ratio": "Current Ratio",
    "quick_ratio": "Quick Ratio",
    "debt_to_equity": "Debt to Equity",
    "interest_coverage": "Interest Coverage",
    "debt_ratio": "Debt Ratio",
    "gross_margin_pct": "Gross Margin %",
    "operating_margin_pct": "Operating Margin %",
    "net_margin_pct": "Net Margin %",
    "return_on_equity": "Return on Equity %",
    "return_on_assets": "Return on Assets %",
    "asset_turnover": "Asset Turnover",
    "receivable_days": "Receivable Days",
    "inventory_days": "Inventory Days",
    "payable_days": "Payable Days",
    "cash_conversion_cycle": "Cash Conversion Cycle",
    "altman_z_proxy": "Altman Z-Score (Proxy)"
  }
}
```

**Verification:** `python -c "import json; json.load(open('apps/api/app/data/industry_benchmarks.json')); print('OK')"`

---

## Task 4: AI Analytics Service (Anomaly Detection + Commentary + Going Concern)

**Files:**
- Create: `apps/api/app/services/afs/analytics_ai.py`

This service uses the LLMRouter to:
1. Detect anomalies by comparing ratios against benchmarks and flagging outliers
2. Generate management commentary suggestions
3. Assess going concern risk factors

Follows the exact same pattern as `disclosure_drafter.py` and `tax_note_drafter.py`.

```python
"""AFS AI Analytics — anomaly detection, commentary suggestions, going concern assessment."""

from __future__ import annotations

from typing import Any

from apps.api.app.services.llm.provider import LLMResponse, Message
from apps.api.app.services.llm.router import LLMRouter


ANOMALY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "anomalies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ratio_key": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                    "description": {"type": "string"},
                    "disclosure_impact": {"type": "string"},
                },
                "required": ["ratio_key", "severity", "description", "disclosure_impact"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["anomalies"],
    "additionalProperties": False,
}

COMMENTARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key_highlights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 key financial highlights for directors' report",
        },
        "risk_factors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Material risk factors to mention",
        },
        "outlook_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Forward-looking commentary suggestions",
        },
    },
    "required": ["key_highlights", "risk_factors", "outlook_points"],
    "additionalProperties": False,
}

GOING_CONCERN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["low", "moderate", "high", "critical"]},
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "factor": {"type": "string"},
                    "indicator": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                    "detail": {"type": "string"},
                },
                "required": ["factor", "indicator", "detail"],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string"},
        "disclosure_required": {"type": "boolean"},
    },
    "required": ["risk_level", "factors", "recommendation", "disclosure_required"],
    "additionalProperties": False,
}


def _format_ratios_for_prompt(ratios: dict, benchmarks: dict | None = None) -> str:
    """Format ratio data into a readable prompt section."""
    lines = ["## Computed Financial Ratios\n"]
    for key, value in ratios.items():
        if key.startswith("_"):
            continue
        if value is None:
            continue
        label = key.replace("_", " ").title()
        bench_info = ""
        if benchmarks and key in benchmarks:
            b = benchmarks[key]
            bench_info = f"  [Industry: p25={b['p25']}, median={b['median']}, p75={b['p75']}]"
        lines.append(f"- {label}: {value}{bench_info}")
    return "\n".join(lines)


async def detect_anomalies(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    entity_name: str,
    ratios: dict,
    benchmarks: dict | None = None,
) -> LLMResponse:
    """Detect unusual ratio values that may require additional disclosure."""
    system = (
        "You are a financial analyst reviewing computed ratios for an entity's annual financial statements. "
        "Identify any unusual or concerning values. Compare against industry benchmarks where provided. "
        "Focus on ratios that deviate significantly from normal ranges or industry norms. "
        "For each anomaly, explain the potential disclosure impact under IFRS/GAAP."
    )
    user = f"Entity: {entity_name}\n\n{_format_ratios_for_prompt(ratios, benchmarks)}"

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=ANOMALY_SCHEMA,
        task_label="afs_anomaly_detection",
        max_tokens=4096,
        temperature=0.2,
    )


async def generate_commentary(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    entity_name: str,
    framework_name: str,
    ratios: dict,
    benchmarks: dict | None = None,
) -> LLMResponse:
    """Generate management commentary suggestions for directors' report."""
    system = (
        f"You are a financial reporting advisor helping prepare the directors' report for {entity_name} "
        f"under {framework_name}. Based on the financial ratios, suggest key talking points, "
        "risk factors, and forward-looking statements. Be specific and reference actual figures."
    )
    user = _format_ratios_for_prompt(ratios, benchmarks)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=COMMENTARY_SCHEMA,
        task_label="afs_management_commentary",
        max_tokens=4096,
        temperature=0.3,
    )


async def assess_going_concern(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    entity_name: str,
    framework_name: str,
    ratios: dict,
) -> LLMResponse:
    """Assess going concern risk factors based on financial ratios."""
    system = (
        f"You are an auditor assessing going concern for {entity_name} under {framework_name}. "
        "Evaluate the financial ratios for indicators of going concern risk per IAS 1 / ASU 2014-15. "
        "Consider: liquidity, solvency, profitability trends, and the Altman Z-score proxy. "
        "Classify risk level and determine if additional disclosure is required."
    )
    user = _format_ratios_for_prompt(ratios)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=GOING_CONCERN_SCHEMA,
        task_label="afs_going_concern",
        max_tokens=4096,
        temperature=0.1,
    )
```

Also add the 3 new task labels to the LLM router default policy:

**Modify:** `apps/api/app/services/llm/router.py` — add after the `afs_tax_note` entries:

```python
{"task_label": "afs_anomaly_detection", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.2},
{"task_label": "afs_anomaly_detection", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.2},
{"task_label": "afs_management_commentary", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.3},
{"task_label": "afs_management_commentary", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.3},
{"task_label": "afs_going_concern", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.1},
{"task_label": "afs_going_concern", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.1},
```

**Verification:** `python -c "from apps.api.app.services.afs.analytics_ai import detect_anomalies, generate_commentary, assess_going_concern; print('OK')"`

---

## Task 5: Backend Analytics Endpoints

**Files:**
- Modify: `apps/api/app/routers/afs.py`

Add 5 new endpoints after the output endpoints. These endpoints are added directly to the existing AFS router (no separate router file needed).

### New ID generator
```python
def _analytics_id() -> str:
    return f"aan_{uuid.uuid4().hex[:14]}"
```

### New Pydantic model
```python
class ComputeAnalyticsBody(BaseModel):
    industry_segment: str = Field(default="general", pattern=r"^[a-z_]+$")
```

### Endpoints

1. **`POST /engagements/{engagement_id}/analytics/compute`** — Compute ratios + run AI analysis
   - Load latest trial balance for engagement
   - Call `compute_from_tb(data_json)` to get ratios
   - Load industry benchmarks from JSON file
   - Call all 3 AI services in parallel: anomaly detection, commentary, going concern
   - Store results in `afs_analytics` table
   - Return the full analytics record

2. **`GET /engagements/{engagement_id}/analytics`** — Get latest analytics
   - Return latest `afs_analytics` row for engagement (ordered by computed_at DESC, LIMIT 1)
   - 404 if none exists

3. **`GET /engagements/{engagement_id}/analytics/ratios`** — Get just ratios
   - Return `ratios_json` from latest analytics

4. **`GET /engagements/{engagement_id}/analytics/anomalies`** — Get just anomalies
   - Return `anomalies_json` from latest analytics

5. **`GET /engagements/{engagement_id}/analytics/going-concern`** — Get going concern assessment
   - Return `going_concern_json` from latest analytics

### Key implementation for compute endpoint:

```python
import asyncio
import json
from pathlib import Path

from apps.api.app.services.afs.ratio_calculator import compute_from_tb
from apps.api.app.services.afs.analytics_ai import detect_anomalies, generate_commentary, assess_going_concern

_BENCHMARKS_PATH = Path(__file__).resolve().parent.parent / "data" / "industry_benchmarks.json"
_BENCHMARKS_CACHE: dict | None = None

def _load_benchmarks() -> dict:
    global _BENCHMARKS_CACHE
    if _BENCHMARKS_CACHE is None:
        with open(_BENCHMARKS_PATH) as f:
            _BENCHMARKS_CACHE = json.load(f)
    return _BENCHMARKS_CACHE

@router.post("/engagements/{engagement_id}/analytics/compute")
async def compute_analytics(
    engagement_id: str,
    body: ComputeAnalyticsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Verify engagement exists
        eng = await conn.fetchrow(
            "SELECT entity_name, framework_id FROM afs_engagements WHERE tenant_id=$1 AND engagement_id=$2",
            x_tenant_id, engagement_id,
        )
        if not eng:
            raise HTTPException(404, "Engagement not found")

        # Get framework name
        fw = await conn.fetchrow(
            "SELECT name FROM afs_frameworks WHERE tenant_id=$1 AND framework_id=$2",
            x_tenant_id, eng["framework_id"],
        )
        framework_name = fw["name"] if fw else "IFRS"

        # Load latest trial balance
        tb = await conn.fetchrow(
            "SELECT data_json FROM afs_trial_balances WHERE tenant_id=$1 AND engagement_id=$2 ORDER BY uploaded_at DESC LIMIT 1",
            x_tenant_id, engagement_id,
        )
        if not tb or not tb["data_json"]:
            raise HTTPException(400, "No trial balance found. Upload one via the Setup page first.")

        data_json = tb["data_json"] if isinstance(tb["data_json"], list) else json.loads(tb["data_json"])

        # Compute ratios
        ratios = compute_from_tb(data_json)

        # Load benchmarks
        benchmarks_data = _load_benchmarks()
        segment = body.industry_segment
        segment_benchmarks = benchmarks_data.get("segments", {}).get(segment, benchmarks_data["segments"]["general"])

        # Benchmark comparison: for each ratio, determine percentile position
        benchmark_comparison = {}
        for key, value in ratios.items():
            if key.startswith("_") or value is None or key not in segment_benchmarks:
                continue
            b = segment_benchmarks[key]
            position = "below_p25" if value < b["p25"] else "p25_to_median" if value < b["median"] else "median_to_p75" if value < b["p75"] else "above_p75"
            benchmark_comparison[key] = {"value": value, "p25": b["p25"], "median": b["median"], "p75": b["p75"], "position": position}

        # Run AI analysis in parallel
        entity_name = eng["entity_name"]
        anomalies_resp, commentary_resp, gc_resp = await asyncio.gather(
            detect_anomalies(llm, x_tenant_id, entity_name=entity_name, ratios=ratios, benchmarks=segment_benchmarks),
            generate_commentary(llm, x_tenant_id, entity_name=entity_name, framework_name=framework_name, ratios=ratios, benchmarks=segment_benchmarks),
            assess_going_concern(llm, x_tenant_id, entity_name=entity_name, framework_name=framework_name, ratios=ratios),
            return_exceptions=True,
        )

        anomalies = anomalies_resp.content if not isinstance(anomalies_resp, Exception) else {"anomalies": [], "_error": str(anomalies_resp)}
        commentary = commentary_resp.content if not isinstance(commentary_resp, Exception) else None
        going_concern = gc_resp.content if not isinstance(gc_resp, Exception) else None

        # Store
        aid = _analytics_id()
        await conn.execute(
            """INSERT INTO afs_analytics (tenant_id, analytics_id, engagement_id, ratios_json, benchmark_comparison_json, anomalies_json, commentary_json, going_concern_json, industry_segment, computed_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            x_tenant_id, aid, engagement_id,
            json.dumps(ratios), json.dumps(benchmark_comparison), json.dumps(anomalies),
            json.dumps(commentary) if commentary else None,
            json.dumps(going_concern) if going_concern else None,
            segment, x_user_id or None,
        )

        row = await conn.fetchrow(
            "SELECT * FROM afs_analytics WHERE tenant_id=$1 AND analytics_id=$2",
            x_tenant_id, aid,
        )

    return _row_to_dict(row)
```

**Verification:** `python -c "from apps.api.app.routers.afs import router; print('OK')"`

---

## Task 6: Frontend API Additions

**Files:**
- Modify: `apps/web/lib/api.ts`

### New TypeScript interfaces

```typescript
export interface AFSAnalytics {
  analytics_id: string;
  engagement_id: string;
  computed_at: string;
  ratios_json: Record<string, number | null>;
  benchmark_comparison_json: Record<string, {
    value: number;
    p25: number;
    median: number;
    p75: number;
    position: string;
  }>;
  anomalies_json: {
    anomalies: {
      ratio_key: string;
      severity: string;
      description: string;
      disclosure_impact: string;
    }[];
  };
  commentary_json: {
    key_highlights: string[];
    risk_factors: string[];
    outlook_points: string[];
  } | null;
  going_concern_json: {
    risk_level: string;
    factors: {
      factor: string;
      indicator: string;
      detail: string;
    }[];
    recommendation: string;
    disclosure_required: boolean;
  } | null;
  industry_segment: string | null;
  status: string;
  error_message: string | null;
  computed_by: string | null;
}
```

### New API methods in `api.afs`

```typescript
// Analytics
computeAnalytics(tenantId, engagementId, body: { industry_segment?: string }) → AFSAnalytics
getAnalytics(tenantId, engagementId) → AFSAnalytics
getAnalyticsRatios(tenantId, engagementId) → Record<string, number | null>
getAnalyticsAnomalies(tenantId, engagementId) → { anomalies: [...] }
getGoingConcern(tenantId, engagementId) → { risk_level: string; ... }
```

Implementation:
```typescript
computeAnalytics: (tenantId: string, engagementId: string, body: { industry_segment?: string }) =>
  request<AFSAnalytics>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/compute`, { tenantId, method: "POST", body }),
getAnalytics: (tenantId: string, engagementId: string) =>
  request<AFSAnalytics>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics`, { tenantId }),
getAnalyticsRatios: (tenantId: string, engagementId: string) =>
  request<Record<string, number | null>>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/ratios`, { tenantId }),
getAnalyticsAnomalies: (tenantId: string, engagementId: string) =>
  request<{ anomalies: { ratio_key: string; severity: string; description: string; disclosure_impact: string }[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/anomalies`, { tenantId }),
getGoingConcern: (tenantId: string, engagementId: string) =>
  request<{ risk_level: string; factors: { factor: string; indicator: string; detail: string }[]; recommendation: string; disclosure_required: boolean }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/going-concern`, { tenantId }),
```

---

## Task 7: Analytics Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/analytics/page.tsx`

### Layout
The page is split into sections, each inside a VACard:

1. **Header:** Back arrow (→ sections) + "{entity_name} — Analytics" + nav buttons (Sections, Tax, Review, Consolidation, Output)

2. **Compute panel** (top):
   - Industry segment selector (dropdown: general, manufacturing, retail, technology, financial_services, mining, construction, healthcare)
   - "Compute Analytics" button → calls `computeAnalytics`, shows spinner
   - Last computed timestamp + status badge

3. **Ratio cards grid** (3-column grid):
   - 4 category groups: Liquidity, Solvency, Profitability, Efficiency
   - Each category is a VACard with heading + table of ratios
   - Each ratio row: label, value (formatted), benchmark comparison bar
   - Benchmark bar: visual indicator showing where value sits relative to p25/median/p75
     - Green if between p25-p75, amber if outside, red if far outside
   - The bar is a simple `<div>` progress bar with a marker dot

4. **Anomalies panel:**
   - List of anomaly cards, each with severity badge (info=default, warning=warning, critical=danger)
   - Shows ratio_key, description, disclosure_impact
   - Empty state if no anomalies

5. **Management Commentary:**
   - Three sections: "Key Highlights", "Risk Factors", "Outlook"
   - Each shows a bulleted list of AI-generated suggestions
   - Null state: "Run analytics to generate commentary"

6. **Going Concern Assessment:**
   - Risk level badge (low=success, moderate=warning, high/critical=danger)
   - Factors table: factor, indicator (positive=green, neutral=default, negative=red), detail
   - Recommendation text
   - Disclosure required: Yes/No badge

### Styling patterns
Same as all other AFS pages — dark theme, VACard, VABadge, VAButton, VASpinner.

### Benchmark comparison bar component (inline)
```tsx
function BenchmarkBar({ value, p25, median, p75 }: { value: number; p25: number; median: number; p75: number }) {
  // Scale value position as percentage within [p25*0.5, p75*1.5] range
  const min = Math.min(p25 * 0.5, value * 0.8);
  const max = Math.max(p75 * 1.5, value * 1.2);
  const range = max - min || 1;
  const pct = Math.max(0, Math.min(100, ((value - min) / range) * 100));
  const p25Pct = ((p25 - min) / range) * 100;
  const medPct = ((median - min) / range) * 100;
  const p75Pct = ((p75 - min) / range) * 100;
  const inRange = value >= p25 && value <= p75;
  const color = inRange ? "bg-emerald-400" : (value < p25 * 0.7 || value > p75 * 1.5) ? "bg-red-400" : "bg-amber-400";

  return (
    <div className="relative h-3 w-full rounded-full bg-va-panel">
      {/* IQR range highlight */}
      <div className="absolute top-0 h-3 rounded-full bg-va-surface" style={{ left: `${p25Pct}%`, width: `${p75Pct - p25Pct}%` }} />
      {/* Median line */}
      <div className="absolute top-0 h-3 w-px bg-va-text2" style={{ left: `${medPct}%` }} />
      {/* Value dot */}
      <div className={`absolute top-0.5 h-2 w-2 rounded-full ${color}`} style={{ left: `${pct}%` }} />
    </div>
  );
}
```

---

## Task 8: Navigation Wiring + Build Verification

**Files:**
- Modify: `apps/web/app/(app)/afs/[id]/sections/page.tsx` — add Analytics nav button
- Modify: `apps/web/app/(app)/afs/[id]/tax/page.tsx` — add Analytics nav button
- Modify: `apps/web/app/(app)/afs/[id]/review/page.tsx` — add Analytics nav button
- Modify: `apps/web/app/(app)/afs/[id]/consolidation/page.tsx` — add Analytics nav button
- Modify: `apps/web/app/(app)/afs/[id]/output/page.tsx` — add Analytics nav button

Add to each page's header button group:
```tsx
<VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/analytics`)}>
  Analytics
</VAButton>
```

### Build verification

1. `python -c "from apps.api.app.routers.afs import router; print('Router OK')"`
2. `python -c "from apps.api.app.services.afs.ratio_calculator import compute_from_tb; print('Ratio OK')"`
3. `python -c "from apps.api.app.services.afs.analytics_ai import detect_anomalies; print('AI OK')"`
4. `cd apps/web && npx next build` — no type errors
5. `cd apps/web && npx vitest run` — all tests pass (140+)

---

## Execution Order

```
Task 1 (Migration 0056)                    ─── first (schema required by all)
Task 2 (Ratio calculator service)          ─┐
Task 3 (Industry benchmark data)           ─┤── parallel after Task 1
Task 4 (AI analytics service)              ─┤
Task 6 (Frontend API additions)            ─┘
Task 5 (Backend endpoints)                 ─── after Tasks 2+3+4
Task 7 (Analytics page)                    ─── after Tasks 5+6
Task 8 (Nav wiring + build verification)   ─── last
```

Tasks 2, 3, 4, 6 are independent — execute in parallel.
Task 5 depends on Tasks 2, 3, 4 (imports all three services).
Task 7 depends on Tasks 5 + 6.
Task 8 depends on Task 7.
