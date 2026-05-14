# Lift

Lift is a local-first incrementality decision agent for campaign analysis.

Current implementation scope:

- Data schema validation for binary treatment campaign data
- Causal trust diagnostics
- Campaign-level incrementality
- Baseline ranking models
- Duality R-learner
- Cost curve, AUCC, iRoI, CPiA evaluation
- Local artifacts under `outputs/<run-id>/`

`references/fractional_uplift` is reference-only and is not a runtime dependency.

## CLI

```bash
python3 -m lift.interfaces.cli inspect data.csv
python3 -m lift.interfaces.cli analyze data.csv --seed 123
python3 -m lift.interfaces.cli outputs
```
