# Lift

Lift is a local-first incrementality decision agent for campaign analysis.

Current implementation scope:

- Data schema validation for binary treatment campaign data
- Causal trust diagnostics
- Campaign-level incrementality
- Baseline ranking models
- Duality R-learner
- scikit-learn based preprocessing, baselines, propensity estimation, and R-learner nuisance models
- Cost curve, AUCC, iRoI, CPiA evaluation
- Local artifacts under `outputs/<run-id>/`
- CLI simulation and target re-export from saved artifacts

`references/fractional_uplift` is reference-only and is not a runtime dependency.

## CLI

Install local dependencies first:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

```bash
.venv/bin/lift inspect data.csv
.venv/bin/lift analyze data.csv --seed 123 --estimate-propensity
.venv/bin/lift simulate <run-id> --budget 100000000 --min-roi 1.5
.venv/bin/lift export-targets <run-id> --budget 100000000 --min-roi 1.5
.venv/bin/lift report <run-id>
.venv/bin/lift outputs
```

## Fixtures

Small local fixtures are available for smoke testing:

```bash
.venv/bin/lift analyze fixtures/randomized_coupon.csv
.venv/bin/lift inspect fixtures/leakage_coupon.csv
```
