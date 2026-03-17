# DTF — Developer Testing Framework

Developer-only CLI tools for Markov model calibration and validation.
**Never import or call these from API routes.**

## Prerequisites

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
export DTF_TENANT_ID="your-tenant-uuid"
```

---

## DTF-A: calibrate.py

### inspect — Print matrix dimensions and top-5 steady-state states

```bash
python tools/dtf/calibrate.py inspect
python tools/dtf/calibrate.py --tenant-id f004fe0c-da81-49ab-afab-9a9a8286211e inspect
```

### validate — Assert all rows sum to 1.0 ± 1e-9

```bash
python tools/dtf/calibrate.py validate
```

Prints `ROW N: PASS (1.0000000000)` or `ROW N: FAIL (1.0100000000)` per row.
Exits with code 1 if any row fails.

### override — Set P(from→to) and re-normalise the row

```bash
python tools/dtf/calibrate.py override --from-state 0 --to-state 1 --probability 0.15
```

Sets the transition probability for state 0 → state 1 to 0.15,
then re-normalises all other probabilities in row 0 so the row sums to 1.0.

### reset — Restore matrix to observed-data baseline

```bash
python tools/dtf/calibrate.py reset
```

On first call: snapshots the current matrix into `pim_markov_transitions_baseline`
and prints "Baseline created — nothing to reset yet."

On subsequent calls: restores the live matrix from the baseline snapshot.

---

## DTF-B: weekly_validator.py

Validates Markov model predictive accuracy using Spearman IC.

```bash
python tools/dtf/weekly_validator.py
python tools/dtf/weekly_validator.py --weeks 8
python tools/dtf/weekly_validator.py --weeks 4 --output /tmp/validation-2026-03-16.json
```

Exits with code 0 if IC ≥ 0.4, code 1 if IC < 0.4.
Reports are written to `tools/dtf/reports/YYYY-MM-DD.json`.

### Report schema

```json
{
  "date": "2026-03-16",
  "weeks_evaluated": 4,
  "ic_score": 0.432100,
  "ic_threshold": 0.4,
  "pass": true,
  "n_observations": 42,
  "details": [...]
}
```

When n < 10: `"pass": null, "reason": "insufficient_data"`.
