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
- Feynman-style first-run model setup, then a Pi-powered natural-language agent shell when running `lift`
- `lift model ...` and `lift agent ...` configuration surfaces for model/auth and Codex/Claude integration

`references/fractional_uplift` is reference-only and is not a runtime dependency.

## Install

One-line installer shape for a published wheel:

```bash
curl -fsSL https://raw.githubusercontent.com/Funbucket/lift/main/scripts/install/install.sh | bash
lift
lift doctor
lift quickstart
```

For local development:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/lift setup
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

Install the local source tree through the launcher script:

```bash
LIFT_PACKAGE=. sh scripts/install/install.sh
```

Install a built wheel through the user launcher script:

```bash
LIFT_PACKAGE=dist/lift_agent-0.1.2-py3-none-any.whl sh scripts/install/install.sh
lift doctor
lift quickstart
```

The installer also supports `LIFT_VERSION`, `LIFT_PACKAGE_URL`, `LIFT_RELEASE_BASE_URL`, `LIFT_HOME`, `LIFT_BIN_DIR`, and `PYTHON_BIN`.

When `node` and `npm` are available, the installer also installs the Feynman/Pi OAuth bridge under `~/.lift/oauth-bridge`. To disable that optional bridge install:

```bash
curl -fsSL https://raw.githubusercontent.com/Funbucket/lift/main/scripts/install/install.sh | LIFT_INSTALL_OAUTH_BRIDGE=0 bash
```

The bridge installs `@clack/prompts` and `@mariozechner/pi-coding-agent`, so `lift setup` uses Feynman-style arrow-key prompts, `lift model login <provider> --method oauth` opens the browser login flow, and `lift` launches the natural-language Pi shell with Lift tools.

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

Run a packaged example end-to-end (uses small fixture values; `budget=5.0` and `min_roi=0.1` match the fixture scale):

```bash
.venv/bin/lift quickstart
```

For real campaign data with budgets in the hundreds of millions, pass explicit constraints:

```bash
.venv/bin/lift analyze data.csv --budget 100000000 --min-roi 1.5 --seed 123
```

Run `lift` with no command to open the natural-language Lift shell:

```text
Lift dashboard...
> 이 캠페인의 incremental ROI는 얼마야? data.csv를 분석해서 알려줘.
> 예산 100000000이면 누구에게 쿠폰을 보내야 해?
```

**Requirements for the natural-language shell:** The Pi shell requires `node` on PATH and
`@mariozechner/pi-coding-agent` installed under `~/.lift/oauth-bridge/`. The installer
handles this automatically when `node` and `npm` are available. If the Pi runtime is not
installed, `lift` falls back to the legacy slash-command REPL with a warning.

Check runtime status with `lift runtime`. If `available: false`, reinstall with the default installer or set `LIFT_INSTALL_OAUTH_BRIDGE=1` and rerun.

The legacy slash-command REPL remains available with `lift repl`.

Lift is designed as a standalone local CLI/runtime. Codex and Claude integration uses Lift skills, prompts, and agent/model configuration commands, not an MCP server.

Model and agent configuration:

```bash
lift model list
lift model login openai --method api-key --api-key "$OPENAI_API_KEY" --model gpt-5.4
lift model login openai-codex --method oauth
lift model set openai/gpt-5.4
lift agent status
lift agent set codex
```

OAuth login follows the Feynman/Pi structure, but requires a Pi-compatible auth bridge. Until that bridge is installed, `lift model login <provider> --method oauth` reports `bridge_required` instead of storing unusable credentials.

Interactive setup starts with the Feynman-style model access choice:

```bash
lift setup
```

```text
┌  Lift setup
│
◆  Choose how to configure model access:
│  ● 1. OAuth login (recommended: ChatGPT Plus/Pro, Claude Pro/Max, Copilot, ...)
│  ○ 2. API key or custom provider (OpenAI, Anthropic, Google, ...)
│  ○ 3. Cancel
```

Bridge commands:

```bash
lift model bridge
lift model bridge-path --raw
```

The bridge opens the provider login URL in the browser, lets the Pi auth layer write credentials to Lift's auth path, and returns authenticated model ids to Lift.

Install Lift guidance into Codex or a repo-local agent directory:

```bash
lift install-skills --target codex
lift install-skills --target repo --project-root .
```

## Fixtures

Small local fixtures are available for smoke testing. These use small numeric values (maximize_kpi ~0–5, constraint_kpi ~0–1); use `--budget` and `--min-roi` appropriate to the fixture scale:

```bash
.venv/bin/lift analyze fixtures/randomized_coupon.csv --seed 123
.venv/bin/lift analyze fixtures/observational_coupon.csv --estimate-propensity --seed 123
.venv/bin/lift analyze fixtures/low_overlap_coupon.csv --seed 123
.venv/bin/lift inspect fixtures/leakage_coupon.csv
```

After analysis, artifacts are written under `~/.lift/outputs/<run-id>/` (installed) or `outputs/<run-id>/` (local dev). Each run produces:

```
run.json              # seed, dataset fingerprint, config, status
schema.json           # inferred column mapping
propensity.json       # propensity source and stats
trust.json            # trust_level, overlap, covariate balance, leakage
campaign_incrementality.json  # campaign-level iROI and CIs
models.json           # model list and primary model
evaluation.json       # AUUC, Qini, cost curve scalars per model
curves.csv            # per-model ranking curves (all targets)
budget-frontier.csv   # cumulative gain/cost/ROI as targets added
policy-scores.csv     # per-unit scores and expected gain/cost from primary model
targets.csv           # budget/ROI filtered target list
simulation.json       # constraint status and expected portfolio metrics
report.md             # human-readable summary
provenance.md         # dataset fingerprint and artifact list
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
PYTHON_BIN=python3 scripts/install/smoke-install.sh
```
