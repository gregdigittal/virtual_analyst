# DG Parity — Phase 4: Business Line Segmentation

> **CRITICAL**: Work in the MAIN repository directory. Do NOT create a git
> worktree. Do NOT modify files outside the scope listed below.

## Context Update

Phases 1-3 are complete. The model now supports:
- Debt schedules with interest (Phase 1)
- Dividends, equity raises, funding waterfall (Phase 2)
- Correlated Monte Carlo sampling via Cholesky (Phase 3)

**Current limitation:** `RevenueStream` (schemas.py:67-79) is flat — no
business line grouping, no launch timing, no ramp-up. Digital Genius supports
hierarchical business lines with market segmentation and staged launches.

## In-Scope Files (ONLY modify these)

| # | File | Action |
|---|------|--------|
| 1 | `shared/fm_shared/model/schemas.py` | Add optional fields to `RevenueStream` |
| 2 | `shared/fm_shared/model/engine.py` | Apply launch/ramp factors to volume drivers |
| 3 | `shared/fm_shared/model/statements.py` | Add `revenue_by_segment` to `Statements` |
| 4 | `tests/unit/test_engine.py` | Add launch/ramp engine tests |
| 5 | `tests/unit/test_statements.py` | Add segment aggregation test |

## Implementation Steps

### Step 1 — Schema: Extend `RevenueStream` (schemas.py:67-79)

Add optional fields **after** the `drivers` field on line 79:

```python
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
    # New optional fields for segmentation and timing:
    business_line: str | None = None
    market: str | None = None
    launch_month: int | None = Field(None, ge=0, description="Month this stream activates (0-indexed)")
    ramp_up_months: int | None = Field(None, ge=1, description="Months to reach full volume after launch")
    ramp_curve: Literal["linear", "s_curve", "step"] = "linear"
```

All new fields are optional with defaults, so backward compat is preserved.

### Step 2 — Engine: Apply launch_month / ramp_up factor (engine.py)

The engine resolves volume drivers at `engine.py:146-152`. We need to
scale volume drivers belonging to streams with `launch_month` set.

#### 2a. Build a volume-driver → ramp-info mapping

Add a helper function:

```python
def _build_ramp_factors(
    assumptions: Assumptions, horizon: int
) -> dict[str, list[float]]:
    """
    For each volume driver ref that belongs to a stream with launch_month,
    compute a per-period scaling factor [0.0 .. 1.0].
    Returns {driver_ref: [factor_t0, factor_t1, ...]}.
    """
    factors: dict[str, list[float]] = {}
    for rs in assumptions.revenue_streams:
        if rs.launch_month is None:
            continue
        for dv in rs.drivers.volume:
            scale = [0.0] * horizon
            for t in range(horizon):
                if t < rs.launch_month:
                    scale[t] = 0.0
                elif rs.ramp_up_months and t < rs.launch_month + rs.ramp_up_months:
                    elapsed = t - rs.launch_month
                    total = rs.ramp_up_months
                    if rs.ramp_curve == "linear":
                        scale[t] = (elapsed + 1) / total
                    elif rs.ramp_curve == "s_curve":
                        # S-curve: scaled sigmoid using 6*x-3 mapping
                        x = (elapsed + 0.5) / total  # midpoint of period
                        import math
                        scale[t] = 1.0 / (1.0 + math.exp(-6 * (2 * x - 1)))
                    elif rs.ramp_curve == "step":
                        scale[t] = 0.0  # step: 0 during ramp, 1 at end
                    else:
                        scale[t] = (elapsed + 1) / total
                else:
                    scale[t] = 1.0
            factors[dv.ref] = scale
    return factors
```

#### 2b. Apply factors in the time-series loop

In `run_engine`, after `drivers_by_ref = _collect_driver_values_by_ref(assumptions)`
(line 119), add:

```python
ramp_factors = _build_ramp_factors(assumptions, horizon)
```

Then modify the driver resolution at lines 148-152:

```python
if node.type == "driver":
    ref = node.ref
    if ref and ref in drivers_by_ref:
        val = _resolve_driver(drivers_by_ref[ref], t)
        if ref in ramp_factors:
            val *= ramp_factors[ref][t]
    else:
        val = 0.0
    time_series[nid][t] = val
```

### Step 3 — Statements: `revenue_by_segment`

#### 3a. Extend the `Statements` dataclass (statements.py:18-23):

```python
@dataclass
class Statements:
    income_statement: list[dict[str, Any]]
    balance_sheet: list[dict[str, Any]]
    cash_flow: list[dict[str, Any]]
    periods: list[str]
    revenue_by_segment: dict[str, list[float]] = field(default_factory=dict)
```

Add `from dataclasses import dataclass, field` at the top (currently only
imports `dataclass`).

#### 3b. Compute segment revenue in `generate_statements`

After line 102 (`revenue, cogs = _revenue_and_cogs_from_timeseries(...)`)
add a segment aggregation:

```python
# Aggregate revenue by business_line
revenue_by_segment: dict[str, list[float]] = {}
for rs in config.assumptions.revenue_streams:
    seg = rs.business_line or "default"
    if seg not in revenue_by_segment:
        revenue_by_segment[seg] = [0.0] * horizon
    # Find output nodes connected to this stream's drivers
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
            # Check if any of this node's formula inputs come from this stream
            formula = next(
                (f for f in config.driver_blueprint.formulas if f.output_node_id == nid),
                None,
            )
            if formula and stream_driver_refs & set(formula.inputs):
                for t in range(horizon):
                    revenue_by_segment[seg][t] += time_series[nid][t]
```

Then pass `revenue_by_segment=revenue_by_segment` into the `Statements`
constructor at the end of `generate_statements`.

### Step 4 — Tests

#### In `tests/unit/test_engine.py`, add:

```python
def test_launch_month_zeros_pre_launch() -> None:
    """Revenue stream with launch_month=6 produces zero revenue before month 6."""
    config = _make_config_with_launch(launch_month=6, ramp_up_months=None)
    ts = run_engine(config)
    rev = ts["n_revenue"]  # adjust node_id to match your fixture
    for t in range(6):
        assert rev[t] == 0.0, f"Period {t} should be 0 before launch"
    for t in range(6, 12):
        assert rev[t] > 0.0, f"Period {t} should have revenue after launch"


def test_linear_ramp_up() -> None:
    """Revenue ramps linearly over ramp_up_months after launch_month."""
    config = _make_config_with_launch(launch_month=3, ramp_up_months=6, ramp_curve="linear")
    ts = run_engine(config)
    rev = ts["n_revenue"]
    # Months 0-2: zero
    for t in range(3):
        assert rev[t] == 0.0
    # Month 3: 1/6 of full, month 4: 2/6, ..., month 8: 6/6 = full
    full_rev = rev[9]  # month 9 is fully ramped
    assert full_rev > 0
    for i, t in enumerate(range(3, 9)):
        expected_factor = (i + 1) / 6
        assert abs(rev[t] - full_rev * expected_factor) < 0.01, (
            f"Period {t}: expected factor {expected_factor}, got {rev[t]/full_rev:.3f}"
        )


def test_s_curve_ramp() -> None:
    """S-curve ramp produces values between 0 and 1, monotonically increasing."""
    config = _make_config_with_launch(launch_month=0, ramp_up_months=6, ramp_curve="s_curve")
    ts = run_engine(config)
    rev = ts["n_revenue"]
    # Should be monotonically increasing during ramp
    for t in range(1, 6):
        assert rev[t] >= rev[t - 1], f"Period {t} should be >= period {t-1}"
    # First period should be < last ramp period
    assert rev[0] < rev[5]


def test_step_ramp() -> None:
    """Step ramp: zero during ramp, full at end of ramp."""
    config = _make_config_with_launch(launch_month=2, ramp_up_months=4, ramp_curve="step")
    ts = run_engine(config)
    rev = ts["n_revenue"]
    for t in range(6):  # months 0-5: either pre-launch or during ramp
        assert rev[t] == 0.0
    assert rev[6] > 0  # month 6: ramp complete


def test_no_launch_month_unchanged() -> None:
    """Stream without launch_month behaves normally (backward compat)."""
    config1 = _make_config_without_launch()
    config2 = _make_config_with_launch(launch_month=None, ramp_up_months=None)
    ts1 = run_engine(config1)
    ts2 = run_engine(config2)
    np.testing.assert_array_almost_equal(ts1["n_revenue"], ts2["n_revenue"])
```

You will need to create `_make_config_with_launch` and `_make_config_without_launch`
helpers based on `minimal_model_config()` from `tests/conftest.py`. These
should create a 12-month config with a single revenue stream whose volume
driver is a constant and set the new RevenueStream fields.

#### In `tests/unit/test_statements.py`, add:

```python
def test_revenue_by_segment() -> None:
    """revenue_by_segment groups revenue by business_line."""
    config = _config_with_segments()  # 2 streams, business_line="retail" and "wholesale"
    ts = run_engine(config)
    stmts = generate_statements(config, ts)
    assert "retail" in stmts.revenue_by_segment
    assert "wholesale" in stmts.revenue_by_segment
    # Total per-segment should sum to total revenue
    for t in range(config.metadata.horizon_months):
        total = sum(
            stmts.revenue_by_segment[seg][t] for seg in stmts.revenue_by_segment
        )
        assert abs(total - stmts.income_statement[t]["revenue"]) < 0.01
```

## Constraints

1. **Do NOT modify any file not listed in the scope table.**
2. **Do NOT create a git worktree.**
3. **Do NOT refactor existing tests** — only add new test functions.
4. **Backward compatibility**: all new RevenueStream fields are optional with
   defaults. Existing configs without these fields must work identically.
5. **All existing tests must still pass** (`python -m pytest tests/ -x`).
6. Run `python -m pytest tests/ -x --tb=short` at the end and report results.

## Verification Checklist

- [ ] `RevenueStream.launch_month` validated as `>= 0` (optional)
- [ ] `RevenueStream.ramp_up_months` validated as `>= 1` (optional)
- [ ] `RevenueStream.ramp_curve` defaults to `"linear"`
- [ ] Revenue is zero before `launch_month`
- [ ] Linear ramp scales (1/N, 2/N, ..., N/N) during ramp_up_months
- [ ] S-curve ramp is monotonically increasing
- [ ] Step ramp is zero during ramp, full at end
- [ ] `Statements.revenue_by_segment` groups by `business_line`
- [ ] Existing configs (no new fields) produce identical output
- [ ] All 385+ existing tests still pass
