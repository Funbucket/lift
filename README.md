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
- YAML/JSON config files for schema, model, budget, and ROI settings

`references/fractional_uplift` is reference-only and is not a runtime dependency.

## Install

For local development:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/lift doctor
.venv/bin/lift quickstart
```

Install from a built wheel with `pipx`:

```bash
PYTHON_BIN=.venv/bin/python scripts/build.sh
pipx install --force dist/lift_agent-0.1.0-py3-none-any.whl
lift doctor
lift quickstart
```

Install a user launcher without `pipx`:

```bash
PYTHON_BIN=python3 sh scripts/install/install.sh
lift doctor
lift quickstart
```

Install a built wheel through the user launcher script:

```bash
LIFT_PACKAGE=dist/lift_agent-0.1.0-py3-none-any.whl sh scripts/install/install.sh
lift doctor
lift quickstart
```

By default, installed runs write artifacts under `~/.lift/outputs`. Override with `--output-root`, `LIFT_HOME`, or `LIFT_OUTPUT_ROOT`.

## CLI

```bash
.venv/bin/lift inspect data.csv
.venv/bin/lift analyze data.csv --seed 123 --estimate-propensity
.venv/bin/lift analyze data.csv --config configs/example.yaml
.venv/bin/lift analyze data.csv --baseline-model random_forest --nuisance-model gradient_boosting
.venv/bin/lift simulate <run-id> --budget 100000000 --min-roi 1.5
.venv/bin/lift export-targets <run-id> --budget 100000000 --min-roi 1.5
.venv/bin/lift report <run-id>
.venv/bin/lift outputs
.venv/bin/lift version
```

Run a packaged example end-to-end:

```bash
.venv/bin/lift quickstart
```

Run `lift` with no command to open the local REPL:

```text
lift> /inspect fixtures/randomized_coupon.csv
lift> /analyze fixtures/randomized_coupon.csv --budget 5 --min-roi 0.1
lift> /outputs
lift> /exit
```

Run the stdio MCP server:

```bash
lift mcp
```

Implemented MCP tools:

- `inspect_dataset`
- `validate_dataset`
- `validate_causal_assumptions`
- `analyze_campaign`
- `simulate_budget`
- `generate_report`
- `export_targets`
- `list_outputs`
- `doctor`

## Fixtures

Small local fixtures are available for smoke testing:

```bash
.venv/bin/lift analyze fixtures/randomized_coupon.csv
.venv/bin/lift analyze fixtures/observational_coupon.csv --estimate-propensity
.venv/bin/lift analyze fixtures/low_overlap_coupon.csv
.venv/bin/lift inspect fixtures/leakage_coupon.csv
```

Supported regression estimators:

- `ridge`
- `random_forest`
- `gradient_boosting`

Config files can set logical column names, feature include/exclude lists, estimator types, and estimator params. See `configs/example.yaml`.

## Build

Create installable wheel and source distribution artifacts:

```bash
PYTHON_BIN=.venv/bin/python scripts/build.sh
ls dist/
```

The build script runs bytecode compilation and the unit test suite before packaging.

Smoke test the built wheel in a clean virtual environment:

```bash
PYTHON_BIN=python3 scripts/smoke-wheel.sh
```
