"""
Pydantic v2 models for model_config_v1 artifact.
Mirrors ARTIFACT_MODEL_CONFIG_SCHEMA.json.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Metadata ---
class Metadata(BaseModel):
    entity_name: str = Field(..., min_length=1)
    entity_description: str | None = None
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    country_iso: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    start_date: str = Field(..., description="YYYY-MM-DD")
    horizon_months: int = Field(..., ge=1, le=120)
    resolution: Literal["monthly", "annual"] = "monthly"
    fiscal_year_end_month: int = Field(12, ge=1, le=12)
    tax_rate: float | None = Field(None, ge=0, le=1)
    initial_cash: float | None = Field(None, ge=0)
    initial_equity: float | None = Field(None, ge=0)


# --- Driver value (time-varying or constant) ---
class SchedulePoint(BaseModel):
    month: int = Field(..., ge=0)
    value: float = Field(...)


class DriverValue(BaseModel):
    ref: str = Field(..., description="e.g. drv:price_per_unit")
    label: str | None = None
    value_type: Literal["constant", "ramp", "seasonal", "step"] = Field(...)
    value: float | None = Field(None, description="Scalar for constant")
    schedule: list[SchedulePoint] | None = Field(None, description="For ramp/step")
    seasonal_factors: list[float] | None = Field(None, min_length=12, max_length=12)
    interpolation: Literal["linear", "step"] = "linear"
    units: str | None = None
    data_type: Literal["number", "percent", "currency", "integer"] = "number"

    @model_validator(mode="after")
    def check_schedule_for_ramp_step(self) -> DriverValue:
        if self.value_type in ("ramp", "step") and not self.schedule:
            raise ValueError("schedule required when value_type is ramp or step")
        return self


# --- Revenue stream ---
class RevenueStreamDrivers(BaseModel):
    volume: list[DriverValue] = Field(default_factory=list)
    pricing: list[DriverValue] = Field(default_factory=list)
    direct_costs: list[DriverValue] = Field(default_factory=list)


class RevenueStream(BaseModel):
    stream_id: str = Field(...)
    label: str = Field(...)
    stream_type: Literal[
        "unit_sale",
        "subscription",
        "transactional",
        "rental",
        "consumable_sale",
        "billable_hours",
        "fixed_fee",
    ] = Field(...)
    drivers: RevenueStreamDrivers = Field(default_factory=RevenueStreamDrivers)


# --- Cost structure ---
class CostItem(BaseModel):
    cost_id: str = Field(...)
    label: str = Field(...)
    category: Literal["cogs", "sga", "rnd", "other_opex"] = Field(...)
    driver: DriverValue = Field(...)


class CostStructure(BaseModel):
    variable_costs: list[CostItem] = Field(default_factory=list)
    fixed_costs: list[CostItem] = Field(default_factory=list)
    depreciation_method: Literal["straight_line", "declining_balance"] = "straight_line"


# --- Working capital ---
class WorkingCapital(BaseModel):
    ar_days: DriverValue = Field(...)
    ap_days: DriverValue = Field(...)
    inv_days: DriverValue = Field(...)
    minimum_cash: float = Field(0, ge=0)


# --- Capex ---
class CapexItem(BaseModel):
    capex_id: str = Field(...)
    label: str = Field(...)
    amount: float = Field(..., ge=0)
    month: int = Field(..., ge=0)
    useful_life_months: int = Field(..., ge=1)
    residual_value: float = Field(0, ge=0)


class Capex(BaseModel):
    items: list[CapexItem] = Field(default_factory=list)


# --- Funding ---
class EquityRaise(BaseModel):
    amount: float = Field(...)
    month: int = Field(..., ge=0)
    label: str | None = None


class DrawRepayPoint(BaseModel):
    month: int = Field(...)
    amount: float = Field(...)


class DebtFacility(BaseModel):
    facility_id: str = Field(...)
    label: str = Field(...)
    type: Literal["term_loan", "revolver", "overdraft"] = Field(...)
    limit: float = Field(..., ge=0)
    interest_rate: float = Field(..., ge=0, le=1)
    draw_schedule: list[DrawRepayPoint] | None = None
    repayment_schedule: list[DrawRepayPoint] | None = None
    is_cash_plug: bool = False


class DividendsPolicy(BaseModel):
    policy: Literal["none", "fixed_amount", "payout_ratio"] = "none"
    value: float | None = None


class Funding(BaseModel):
    equity_raises: list[EquityRaise] = Field(default_factory=list)
    debt_facilities: list[DebtFacility] = Field(default_factory=list)
    dividends: DividendsPolicy | None = None


# --- Assumptions (root) ---
class Assumptions(BaseModel):
    revenue_streams: list[RevenueStream] = Field(..., min_length=1)
    cost_structure: CostStructure = Field(default_factory=CostStructure)
    working_capital: WorkingCapital = Field(...)
    capex: Capex | None = None
    funding: Funding | None = None
    staffing: dict[str, Any] | None = None
    custom: dict[str, Any] | None = None


# --- Driver blueprint ---
class BlueprintNode(BaseModel):
    node_id: str = Field(...)
    type: Literal["driver", "formula", "output"] = Field(...)
    label: str = Field(...)
    ref: str | None = Field(None, description="Driver ref for driver nodes")
    classification: str | None = Field(None, description="Statement line: revenue, cogs, opex, capex")


class BlueprintEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    to: str = Field(...)


class BlueprintFormula(BaseModel):
    formula_id: str = Field(...)
    output_node_id: str = Field(...)
    expression: str = Field(...)
    inputs: list[str] = Field(..., description="Node IDs or driver refs")
    notes: str | None = None


class DriverBlueprint(BaseModel):
    nodes: list[BlueprintNode] = Field(...)
    edges: list[BlueprintEdge] = Field(...)
    formulas: list[BlueprintFormula] = Field(...)


# --- Distributions, scenarios, evidence, integrity ---
class DistributionConfig(BaseModel):
    ref: str = Field(...)
    family: Literal["triangular", "normal", "lognormal", "uniform", "pert"] = Field(...)
    params: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None


class ScenarioOverride(BaseModel):
    ref: str = Field(...)
    field: Literal["value", "multiplier"] = Field(...)
    value: float = Field(...)
    target_ref_version: str | None = None
    notes: str | None = None


class Scenario(BaseModel):
    scenario_id: str = Field(...)
    label: str = Field(...)
    description: str | None = None
    overrides: list[ScenarioOverride] = Field(default_factory=list)


class EvidenceEntry(BaseModel):
    assumption_path: str = Field(...)
    source: str = Field(..., max_length=500)
    confidence: Literal["high", "medium", "low", "unvalidated"] = Field(...)
    proposed_by: Literal["user", "llm"] | None = None
    accepted_by: str | None = None
    accepted_at: str | None = None


class IntegrityCheck(BaseModel):
    check_id: str = Field(...)
    severity: Literal["info", "warning", "error"] = Field(...)
    message: str = Field(..., max_length=1000)
    details: dict[str, Any] | None = None


class IntegrityBlock(BaseModel):
    status: Literal["passed", "warning", "failed"] = Field(...)
    checks: list[IntegrityCheck] = Field(default_factory=list)


# --- Root: model_config_v1 ---
class ModelConfig(BaseModel):
    artifact_type: Literal["model_config_v1"] = "model_config_v1"
    artifact_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    tenant_id: str = Field(...)
    baseline_id: str = Field(...)
    baseline_version: str = Field(...)
    created_at: str = Field(..., description="ISO date-time")
    created_by: str | None = None
    parent_baseline_id: str | None = None
    parent_baseline_version: str | None = None
    template_id: str | None = None
    metadata: Metadata = Field(...)
    assumptions: Assumptions = Field(...)
    driver_blueprint: DriverBlueprint = Field(...)
    distributions: list[DistributionConfig] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    evidence_summary: list[EvidenceEntry] = Field(default_factory=list)
    integrity: IntegrityBlock = Field(...)

    @field_validator("created_at")
    @classmethod
    def created_at_iso(cls, v: str) -> str:
        if v and "T" not in v:
            v = f"{v}T00:00:00Z"
        return v
