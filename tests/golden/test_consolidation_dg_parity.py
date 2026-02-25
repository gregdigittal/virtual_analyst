"""Integration test: consolidation engine with multi-entity DG parity scenario.

Three entities:
- Holding (USD, 100% parent)
- Sub A (GBP, 80% owned → 20% NCI)
- Sub B (KES, 100% owned, waterfall-funded)

Intercompany: management_fee Sub A→Holding, loan Holding→Sub B.
"""

from __future__ import annotations

from typing import Any

import pytest

from shared.fm_shared.analysis.consolidation import (
    ConsolidatedResult,
    EntityResult,
    consolidate,
    compute_intercompany_amounts,
    translate_statements,
)
from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.statements import Statements

HORIZON = 12
FLOAT_TOL = 0.02

# ── FX rates ────────────────────────────────────────────────────────────
FX_AVG = {("GBP", "USD"): 1.27, ("KES", "USD"): 0.0077}
FX_CLOSING = {("GBP", "USD"): 1.25, ("KES", "USD"): 0.0077}

# ── Intercompany links ──────────────────────────────────────────────────
IC_LINKS = [
    {
        "from_entity_id": "sub_a",
        "to_entity_id": "holding",
        "link_type": "management_fee",
        "amount_or_rate": 500.0,
        "frequency": "monthly",
        "withholding_tax_applicable": False,
    },
    {
        "from_entity_id": "holding",
        "to_entity_id": "sub_b",
        "link_type": "loan",
        "amount_or_rate": 0.08,
        "frequency": "annual",
        "withholding_tax_applicable": False,
    },
]


# ── Config builders ─────────────────────────────────────────────────────
def _base_config(
    *,
    entity_name: str,
    currency: str,
    tax_rate: float,
    initial_cash: float,
    initial_equity: float,
    units: float,
    price: float,
    fixed_costs: list[dict[str, Any]] | None = None,
    funding: dict[str, Any] | None = None,
    extra_blueprint_nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nodes = [
        {"node_id": "n_units", "type": "driver", "label": "Units", "ref": "drv:units"},
        {"node_id": "n_price", "type": "driver", "label": "Price", "ref": "drv:price"},
        {"node_id": "n_revenue", "type": "output", "label": "Revenue"},
    ]
    if extra_blueprint_nodes:
        nodes.extend(extra_blueprint_nodes)
    d: dict[str, Any] = {
        "artifact_type": "model_config_v1",
        "artifact_version": "1.0.0",
        "tenant_id": "t_test",
        "baseline_id": "bl_consol",
        "baseline_version": "v1",
        "created_at": "2026-01-01T00:00:00Z",
        "metadata": {
            "entity_name": entity_name,
            "currency": currency,
            "start_date": "2026-01-01",
            "horizon_months": HORIZON,
            "tax_rate": tax_rate,
            "initial_cash": initial_cash,
            "initial_equity": initial_equity,
        },
        "assumptions": {
            "revenue_streams": [
                {
                    "stream_id": "rs1",
                    "label": "Revenue",
                    "stream_type": "unit_sale",
                    "drivers": {
                        "volume": [
                            {"ref": "drv:units", "value_type": "constant", "value": units},
                            {"ref": "drv:price", "value_type": "constant", "value": price},
                        ],
                        "pricing": [],
                        "direct_costs": [],
                    },
                }
            ],
            "cost_structure": {
                "variable_costs": [],
                "fixed_costs": fixed_costs or [],
            },
            "working_capital": {
                "ar_days": {"ref": "drv:ar_days", "value_type": "constant", "value": 30.0},
                "ap_days": {"ref": "drv:ap_days", "value_type": "constant", "value": 30.0},
                "inv_days": {"ref": "drv:inv_days", "value_type": "constant", "value": 30.0},
            },
        },
        "driver_blueprint": {
            "nodes": nodes,
            "edges": [
                {"from": "n_units", "to": "n_revenue"},
                {"from": "n_price", "to": "n_revenue"},
            ],
            "formulas": [
                {
                    "formula_id": "f_rev",
                    "output_node_id": "n_revenue",
                    "expression": "units * price",
                    "inputs": ["drv:units", "drv:price"],
                }
            ],
        },
        "scenarios": [],
        "integrity": {"status": "passed", "checks": []},
    }
    if funding:
        d["assumptions"]["funding"] = funding
    return d


def _holding_config_dict() -> dict[str, Any]:
    return _base_config(
        entity_name="Holding Co",
        currency="USD",
        tax_rate=0.25,
        initial_cash=200_000.0,
        initial_equity=500_000.0,
        units=200.0,
        price=50.0,
    )


def _sub_a_config_dict() -> dict[str, Any]:
    return _base_config(
        entity_name="Sub A",
        currency="GBP",
        tax_rate=0.20,
        initial_cash=50_000.0,
        initial_equity=100_000.0,
        units=100.0,
        price=30.0,
        fixed_costs=[
            {
                "cost_id": "fc_sga",
                "label": "SGA",
                "category": "sga",
                "driver": {"ref": "drv:sga_cost", "value_type": "constant", "value": 500.0},
            }
        ],
    )


def _sub_b_config_dict() -> dict[str, Any]:
    return _base_config(
        entity_name="Sub B",
        currency="KES",
        tax_rate=0.30,
        initial_cash=10_000.0,
        initial_equity=5_000_000.0,
        units=500.0,
        price=200.0,
        fixed_costs=[
            {
                "cost_id": "fc_cogs",
                "label": "COGS Direct",
                "category": "cogs",
                "driver": {"ref": "drv:cogs", "value_type": "constant", "value": 20_000.0},
            }
        ],
        funding={
            "equity_raises": [],
            "debt_facilities": [
                {
                    "facility_id": "rev_1",
                    "label": "Revolver",
                    "type": "revolver",
                    "limit": 2_000_000.0,
                    "interest_rate": 0.15,
                    "draw_schedule": [],
                    "repayment_schedule": [],
                    "is_cash_plug": True,
                }
            ],
            "dividends": None,
        },
    )


# ── Conversion helper ───────────────────────────────────────────────────
def _statements_to_consolidation_format(stmts: Statements) -> dict[str, Any]:
    """Convert Statements (list of period-dicts) → consolidation format (label→list)."""

    def _convert(period_dicts: list[dict[str, Any]]) -> dict[str, list[float]]:
        if not period_dicts:
            return {}
        keys = [k for k in period_dicts[0] if isinstance(period_dicts[0][k], (int, float))]
        return {
            k: [float(d.get(k, 0.0)) for d in period_dicts]
            for k in keys
        }

    return {
        "income_statement": _convert(stmts.income_statement),
        "balance_sheet": _convert(stmts.balance_sheet),
        "cash_flow": _convert(stmts.cash_flow),
    }


# ── Module-scoped fixtures ──────────────────────────────────────────────
@pytest.fixture(scope="module")
def holding_stmts() -> Statements:
    cfg = ModelConfig.model_validate(_holding_config_dict())
    return generate_statements(cfg, run_engine(cfg))


@pytest.fixture(scope="module")
def sub_a_stmts() -> Statements:
    cfg = ModelConfig.model_validate(_sub_a_config_dict())
    return generate_statements(cfg, run_engine(cfg))


@pytest.fixture(scope="module")
def sub_b_stmts() -> Statements:
    cfg = ModelConfig.model_validate(_sub_b_config_dict())
    return generate_statements(cfg, run_engine(cfg))


@pytest.fixture(scope="module")
def entity_results(
    holding_stmts: Statements,
    sub_a_stmts: Statements,
    sub_b_stmts: Statements,
) -> list[EntityResult]:
    return [
        EntityResult(
            entity_id="holding",
            currency="USD",
            statements=_statements_to_consolidation_format(holding_stmts),
            kpis={},
            ownership_pct=100.0,
            consolidation_method="full",
        ),
        EntityResult(
            entity_id="sub_a",
            currency="GBP",
            statements=_statements_to_consolidation_format(sub_a_stmts),
            kpis={},
            ownership_pct=80.0,
            consolidation_method="full",
        ),
        EntityResult(
            entity_id="sub_b",
            currency="KES",
            statements=_statements_to_consolidation_format(sub_b_stmts),
            kpis={},
            ownership_pct=100.0,
            consolidation_method="full",
        ),
    ]


@pytest.fixture(scope="module")
def eliminations(entity_results: list[EntityResult]) -> list:
    return compute_intercompany_amounts(IC_LINKS, entity_results, HORIZON, "monthly")


@pytest.fixture(scope="module")
def consolidated(
    entity_results: list[EntityResult],
    eliminations: list,
) -> ConsolidatedResult:
    return consolidate(
        entity_results=entity_results,
        eliminations=eliminations,
        reporting_currency="USD",
        fx_avg_rates=FX_AVG,
        minority_interest_treatment="full",
        horizon=HORIZON,
        eliminate_intercompany=True,
        org_id="org_test",
        fx_closing_rates=FX_CLOSING,
    )


# ── Standalone entity tests ─────────────────────────────────────────────
def test_standalone_holding_revenue(holding_stmts: Statements) -> None:
    """Holding: 200 units * $50 = $10,000 revenue every period."""
    for t in range(HORIZON):
        assert holding_stmts.income_statement[t]["revenue"] == 10_000.0


def test_standalone_sub_a_revenue(sub_a_stmts: Statements) -> None:
    """Sub A: 100 units * £30 = £3,000 revenue, £500 SGA opex."""
    for t in range(HORIZON):
        assert sub_a_stmts.income_statement[t]["revenue"] == 3_000.0
        assert sub_a_stmts.income_statement[t]["gross_profit"] == 3_000.0
        assert sub_a_stmts.income_statement[t]["operating_expenses"] == 500.0


def test_standalone_sub_b_waterfall_triggers(sub_b_stmts: Statements) -> None:
    """Sub B: low initial cash forces waterfall draws; BS balances every period."""
    has_draws = any(
        row.get("debt_draws", 0) > 0 or row.get("financing", 0) != 0
        for row in sub_b_stmts.cash_flow
    )
    assert has_draws, "Waterfall should inject cash into Sub B"
    for t, row in enumerate(sub_b_stmts.balance_sheet):
        assert abs(row["total_assets"] - row["total_liabilities_equity"]) < FLOAT_TOL, (
            f"Sub B BS imbalance at period {t}"
        )


# ── Consolidation tests ─────────────────────────────────────────────────
def _is_data(consolidated: ConsolidatedResult) -> dict[str, list[float]]:
    """Extract IS label→values from consolidated result."""
    from shared.fm_shared.analysis.consolidation import _get_period_values

    return _get_period_values(consolidated.consolidated_is.get("income_statement", {}), HORIZON)


def _bs_data(consolidated: ConsolidatedResult) -> dict[str, list[float]]:
    from shared.fm_shared.analysis.consolidation import _get_period_values

    return _get_period_values(consolidated.consolidated_bs.get("balance_sheet", {}), HORIZON)


def test_consolidated_is_eliminates_ic_revenue(consolidated: ConsolidatedResult) -> None:
    """IC management_fee elimination creates offsetting IC revenue/expense lines."""
    is_d = _is_data(consolidated)
    assert "Intercompany revenue" in is_d, f"Missing IC revenue line. Keys: {list(is_d.keys())}"
    assert "Intercompany expense" in is_d, f"Missing IC expense line. Keys: {list(is_d.keys())}"
    for t in range(HORIZON):
        assert is_d["Intercompany revenue"][t] == is_d["Intercompany expense"][t], (
            f"IC revenue and expense should offset at period {t}"
        )
        assert is_d["Intercompany revenue"][t] < 0, "IC elimination should be negative"


def test_consolidated_nci_sub_a(
    consolidated: ConsolidatedResult,
    sub_a_stmts: Statements,
) -> None:
    """NCI = 20% of Sub A's net income (translated at avg GBP/USD rate)."""
    nci_profit = consolidated.minority_interest["nci_profit"]
    assert any(v != 0 for v in nci_profit), "NCI profit should be non-zero"
    for t in range(HORIZON):
        sub_a_ni = sub_a_stmts.income_statement[t]["net_income"]
        expected_nci = sub_a_ni * 0.20 * FX_AVG[("GBP", "USD")]
        assert abs(nci_profit[t] - expected_nci) < 1.0, (
            f"Period {t}: NCI {nci_profit[t]:.2f} != expected {expected_nci:.2f}"
        )


def test_consolidated_bs_ic_loan_eliminated(consolidated: ConsolidatedResult) -> None:
    """IC loan creates offsetting receivable/payable and interest income/expense."""
    bs_d = _bs_data(consolidated)
    assert "Intercompany loan receivable" in bs_d, f"Missing IC loan recv. Keys: {list(bs_d.keys())}"
    assert "Intercompany loan payable" in bs_d, f"Missing IC loan pay. Keys: {list(bs_d.keys())}"
    for t in range(HORIZON):
        assert bs_d["Intercompany loan receivable"][t] < 0, "IC loan receivable should be eliminated (negative)"
        assert bs_d["Intercompany loan payable"][t] < 0, "IC loan payable should be eliminated (negative)"
        assert abs(bs_d["Intercompany loan receivable"][t] - bs_d["Intercompany loan payable"][t]) < FLOAT_TOL

    is_d = _is_data(consolidated)
    assert "Intercompany interest income" in is_d
    assert "Intercompany interest expense" in is_d


def test_fx_translation_is_at_avg_bs_at_closing(sub_a_stmts: Statements) -> None:
    """Sub A GBP→USD: IS at avg rate (1.27), BS at closing rate (1.25)."""
    stmts_dict = _statements_to_consolidation_format(sub_a_stmts)
    translated = translate_statements(
        stmts_dict,
        from_currency="GBP",
        to_currency="USD",
        fx_avg_rates=FX_AVG,
        fx_closing_rates=FX_CLOSING,
        horizon=HORIZON,
    )
    from shared.fm_shared.analysis.consolidation import _get_period_values

    is_translated = _get_period_values(translated.get("income_statement", {}), HORIZON)
    bs_translated = _get_period_values(translated.get("balance_sheet", {}), HORIZON)

    gbp_revenue = sub_a_stmts.income_statement[0]["revenue"]
    expected_is_rev = gbp_revenue * 1.27
    if "revenue" in is_translated:
        assert abs(is_translated["revenue"][0] - expected_is_rev) < 1.0, (
            f"IS revenue: {is_translated['revenue'][0]:.2f} != {expected_is_rev:.2f}"
        )

    gbp_cash = sub_a_stmts.balance_sheet[0]["cash"]
    expected_bs_cash = gbp_cash * 1.25
    if "cash" in bs_translated:
        assert abs(bs_translated["cash"][0] - expected_bs_cash) < 1.0, (
            f"BS cash: {bs_translated['cash'][0]:.2f} != {expected_bs_cash:.2f}"
        )


def test_consolidated_integrity_no_errors(consolidated: ConsolidatedResult) -> None:
    """No errors; no period mismatch warnings (all entities 12mo)."""
    assert consolidated.integrity["errors"] == []
    for w in consolidated.integrity.get("warnings", []):
        assert "period_mismatch" not in w.lower(), f"Unexpected period mismatch: {w}"


def test_cta_present_for_foreign_subs() -> None:
    """FX translation produces translation_reserve (CTA) for foreign subs."""
    for config_fn, ccy in [(_sub_a_config_dict, "GBP"), (_sub_b_config_dict, "KES")]:
        cfg = ModelConfig.model_validate(config_fn())
        stmts = generate_statements(cfg, run_engine(cfg))
        stmts_dict = _statements_to_consolidation_format(stmts)
        translated = translate_statements(
            stmts_dict,
            from_currency=ccy,
            to_currency="USD",
            fx_avg_rates=FX_AVG,
            fx_closing_rates=FX_CLOSING,
            horizon=HORIZON,
        )
        assert "translation_reserve" in translated, (
            f"Missing translation_reserve for {ccy} entity"
        )
        assert len(translated["translation_reserve"]) == HORIZON
