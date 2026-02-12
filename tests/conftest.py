"""Shared test fixtures and helpers."""

from __future__ import annotations

from shared.fm_shared.model import ModelConfig


def minimal_model_config_dict(
    *,
    tenant_id: str = "t_test",
    horizon_months: int = 12,
    tax_rate: float = 0.0,
    initial_cash: float = 0.0,
    initial_equity: float = 1000.0,
    units: float = 100.0,
    price: float = 10.0,
) -> dict:
    """Minimal model_config_v1 dict — single revenue stream, no costs."""
    return {
        "artifact_type": "model_config_v1",
        "artifact_version": "1.0.0",
        "tenant_id": tenant_id,
        "baseline_id": "bl_placeholder",
        "baseline_version": "v1",
        "created_at": "2026-01-01T00:00:00Z",
        "metadata": {
            "entity_name": "Test",
            "currency": "USD",
            "start_date": "2026-01-01",
            "horizon_months": horizon_months,
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
            "cost_structure": {"variable_costs": [], "fixed_costs": []},
            "working_capital": {
                "ar_days": {"ref": "drv:ar_days", "value_type": "constant", "value": 30.0},
                "ap_days": {"ref": "drv:ap_days", "value_type": "constant", "value": 30.0},
                "inv_days": {"ref": "drv:inv_days", "value_type": "constant", "value": 30.0},
            },
        },
        "driver_blueprint": {
            "nodes": [
                {"node_id": "n_units", "type": "driver", "label": "Units", "ref": "drv:units"},
                {"node_id": "n_price", "type": "driver", "label": "Price", "ref": "drv:price"},
                {"node_id": "n_revenue", "type": "output", "label": "Revenue"},
            ],
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


def minimal_model_config(**kwargs: object) -> ModelConfig:
    """Minimal ModelConfig Pydantic object."""
    return ModelConfig.model_validate(minimal_model_config_dict(**kwargs))
