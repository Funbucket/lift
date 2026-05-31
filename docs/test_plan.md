# Lift Test Plan

## Core Model, Evaluation, UX, and Trust Validation

---

# 1. Purpose

이 문서는 Lift가 PRD/TRD의 핵심 요구사항을 만족하는지 검증하기 위한 테스트 계획이다. 테스트의 중심은 다음이다.

- `fractional_uplift` 없이 core workflow가 동작하는가
- Baselines와 Duality R-learner가 실행되는가
- Cost Curve, AUCC, iRoI, CPiA가 정확하게 계산되는가
- 예산/ROI 제약을 위반하지 않는 target list가 생성되는가
- Feynman식 CLI/REPL UX가 같은 core engine을 사용하는가
- Feynman식 model/agent 설정 명령이 안전한 상태를 보고하는가
- Codex/Claude skills가 Lift CLI와 artifact를 올바르게 안내하는가

---

# 2. Test Scope

## 2.1 In scope

- binary treatment randomized experiment
- binary treatment observational data
- schema inference and mapping
- causal trust diagnostics
- campaign-level incrementality
- core model training
- ranking evaluation
- budget simulation
- target export
- report/provenance artifact
- CLI, REPL, installer, skills smoke tests
- terminal dashboard smoke tests
- model and agent configuration tests

## 2.2 Out of scope for MVP

- multi-treatment production-quality optimization
- continuous treatment dose-response
- online serving latency
- external warehouse connector
- automated campaign execution

---

# 3. Reference Handling Tests

## REF-001: No runtime dependency on archived fractional uplift

Given a clean Lift environment  
When installing Lift core dependencies  
Then `fractional-uplift` must not be installed as a required dependency

Pass criteria:

- package import graph does not require `fractional_uplift`
- core tests pass when `references/fractional_uplift` is absent
- docs state that fractional uplift is reference-only

## REF-002: Reference parity smoke test

Given a small synthetic dataset matching the fractional uplift schema  
When running Lift's internal fractional objective evaluator  
Then score ordering should be directionally consistent with the reference formula

Pass criteria:

- denominator guard is tested
- infinite score handling is tested
- offset KPI and offset scale are tested

---

# 4. Test Datasets

## 4.1 Randomized binary coupon

Purpose:

- baseline end-to-end happy path

Columns:

```
unit_id
treatment
treatment_propensity
conversion
spend
cost
sample_weight
feature_1
...
feature_n
```

Expected:

- trust level: `high`
- campaign-level iRoI is estimable
- core models produce score columns
- target export succeeds

## 4.2 Cost-sensitive randomized coupon

Purpose:

- verify cost-aware models differ from single-KPI uplift

Expected:

- high uplift/high cost cohort is not always top-ranked
- cost-aware models outperform maximize-only T-learner on iRoI at fixed budget
- AUCC is above random baseline

## 4.3 ROI-constrained conversion

Purpose:

- verify `constraint_offset_kpi` and `constraint_offset_scale`

Setup:

```
maximize_kpi = conversion
constraint_kpi = cost
constraint_offset_kpi = spend
constraint_offset_scale = 2.0
```

Expected:

- exported policy respects min iRoI target where feasible
- report states infeasible if no threshold satisfies target

## 4.4 Observational coupon

Purpose:

- verify propensity estimation and trust warning

Expected:

- trust level: `medium` or `low`
- propensity is estimated with cross-fitting
- overlap diagnostics are generated
- hidden confounding warning appears in report

## 4.5 Low-overlap observational

Purpose:

- verify positivity violation handling

Expected:

- trust level: `low` or `blocked`
- overlap warning identifies affected segments
- model training is blocked or marked low-trust

## 4.6 Leakage dataset

Purpose:

- verify post-treatment feature detection

Leakage candidates:

```
coupon_clicked
coupon_used
post_campaign_purchase_count
revenue_after_coupon
membership_tier_updated_after_campaign
```

Expected:

- leakage columns are excluded from covariates by default
- report lists leakage warnings

## 4.7 Negative uplift dataset

Purpose:

- verify do-not-treat behavior

Expected:

- negative uplift cohort is excluded from target list
- report includes do-not-treat segment

---

# 5. Unit Test Plan

## 5.1 Data and schema

Test cases:

- required columns missing
- non-binary treatment
- propensity outside `(0, 1)`
- negative cost
- duplicated `unit_id`
- mixed numeric/categorical features
- missing KPI values

Pass criteria:

- invalid inputs return structured errors
- warnings are deterministic
- schema mapping is persisted to `schema.json`

## 5.2 Propensity and trust

Test cases:

- constant propensity for randomized data
- estimated propensity for observational data
- clipping boundaries
- low overlap segment
- covariate balance before/after weighting

Pass criteria:

- `trust.json` contains all diagnostics
- blocked cases do not silently continue

## 5.3 Campaign incrementality

Test cases:

- difference in means for randomized data
- incremental iRoI
- confidence interval calculation
- zero-cost campaign
- negative incremental gain

Pass criteria:

- division by zero is handled
- confidence interval is omitted or marked unsupported when assumptions do not hold

## 5.4 Cost curve evaluator

Test cases:

- random ranking baseline
- perfect synthetic ranking
- reversed ranking
- ties in score
- variable treatment propensity

Pass criteria:

- cumulative gain/cost are monotonic where expected
- AUCC random baseline is near expected random value
- evaluator output is deterministic under fixed seed

## 5.5 Fractional objective helpers

Test cases:

- no offset KPI
- offset KPI with scale
- denominator near zero
- negative denominator
- infinite score replacement for distillation

Pass criteria:

- no NaN leaks into exported artifacts
- score policy is documented in `models.json`

## 5.6 Terminal runtime and auth surface

Test cases:

- `lift` with no command starts model setup first on an interactive TTY when no default model exists
- `lift` with no command launches the Pi natural-language shell after model setup, or when a default model already exists
- `lift <natural-language prompt>` forwards the prompt into the Pi shell
- `lift runtime` reports Pi CLI, Lift extension, prompt template, and session paths
- `/help`, `/doctor`, `/outputs`, and `/setup` return deterministic output
- `lift model list` reports API-key providers, OAuth providers, current model, and bridge status
- `lift model bridge` reports bundled and installer-managed bridge paths
- `lift model bridge-path --raw` returns a filesystem path that exists after wheel install
- `lift setup` on a TTY starts with OAuth/API-key/Cancel model access choices
- `lift setup --non-interactive` and non-TTY setup keep structured JSON output
- `lift model login <provider> --method api-key` writes `auth.json` and default model settings
- `lift model login <provider> --method oauth` returns `bridge_required` when no Pi-compatible auth bridge is configured
- `lift model login <provider> --method oauth` calls `LIFT_OAUTH_BRIDGE` when configured and persists successful OAuth provider metadata
- OAuth bridge failures return structured `bridge_failed` or bridge-provided error payloads
- `lift agent status` detects Codex/Claude binaries without requiring them
- `lift agent set codex` and `lift agent set claude` persist the default agent
- **Second `lift` run after setup completes does NOT repeat model setup prompt**

Pass criteria:

- no MCP command is exposed
- OAuth login never reports success without a real bridge
- bridge stdout must be valid JSON on success
- existing analysis, simulation, report, and quickstart tests continue to pass

## 5.7 Doctor runtime coverage

Test cases:

- `lift doctor` output includes `node` availability (true/false)
- `lift doctor` output includes Pi CLI path and availability
- `lift doctor` output includes OAuth bridge path and availability
- `lift doctor` status is `warning` when Pi CLI is not installed

Pass criteria:

- A user can determine from `lift doctor` whether the natural-language shell will work
- `status: ok` only when Python deps, node, Pi CLI, and OAuth bridge are all present

---

# 5.8 핵심 사용자 질문 시나리오 테스트

이 섹션은 PRD 12절의 핵심 사용자 질문 10개가 Lift를 통해 답변 가능한지 검증한다. Pi 자연어 shell이 없는 환경에서는 동등한 CLI 명령 시퀀스로 대체한다.

## Q1: "이 캠페인의 incremental ROI는 얼마야?"

Setup:

```
dataset: fixtures/randomized_coupon.csv
```

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
# → campaign_incrementality.json의 incremental_roi 확인
```

Pass criteria:

- `campaign_incrementality.json` 존재하며 `incremental_roi` 필드가 유한한 숫자
- `report.md`의 "Campaign Incrementality" 섹션에 값이 포함됨
- `trust_level` 이 `high` (randomized fixture)

## Q2: "예산 1억이면 누구에게 쿠폰을 보내야 해?"

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --budget 100000000 --seed 123
# 또는 별도 simulate:
lift simulate <run-id> --budget 100000000
```

Pass criteria:

- `targets.csv`의 `expected_incremental_cost` 합계 ≤ 100000000
- `simulation.json`의 `constraint_status = satisfied` 또는 infeasible 명시
- `targets.csv`에 `unit_id`, `rank`, `score`, `recommended_treatment=1` 포함

## Q3: "iRoI 2.0을 유지하면서 incremental conversion을 최대화해줘."

Test:

```bash
lift simulate <run-id> --min-roi 2.0
```

Pass criteria:

- `simulation.json`의 `expected_incremental_roi ≥ 2.0` when feasible
- infeasible인 경우 `constraint_status = failed` 및 이유 포함
- `targets.csv`의 greedy 결과가 min_roi 제약을 위반하지 않음

**Note:** 현재 구현은 greedy 근사. 전역 최적이 아닐 수 있음. 이 한계가 report.md에 반영되어야 한다.

## Q4: "단순 uplift 모델과 cost-aware 모델의 추천 대상은 얼마나 달라?"

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
# evaluation.json의 leaderboard 및 curves.csv에서 모델별 auuc/qini 비교
```

Pass criteria:

- `evaluation.json`의 `leaderboard`에 최소 4개 모델 포함 (baselines + duality_r_learner)
- `curves.csv`에 `model` 컬럼으로 각 모델의 커브가 구분됨
- `duality_r_learner`와 `response_model` 간 AUUC 차이가 데이터에 따라 유의미

**Gap:** `/compare-models` tool 없음. 자연어 질문 시 LLM이 evaluation.json을 직접 읽어야 함.

## Q5: "쿠폰이 손해인 고객군은 누구야?"

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
# policy-scores.csv에서 expected_incremental_profit < 0 인 unit_id 확인
```

Pass criteria:

- `policy-scores.csv`에 모든 고객의 `expected_incremental_gain`, `expected_incremental_cost`, `expected_incremental_profit` 포함
- `expected_incremental_profit < 0` 인 고객 리스트를 도출 가능

**Gap (v0.1.7):** `targets.csv`에는 이 고객들이 포함되지 않음. anti-target export 기능 미구현. 자연어 질문에 자동으로 답하려면 Pi tool이 `policy-scores.csv`를 읽고 필터링해야 함.

## Q6: "이 데이터로 인과추론 결과를 믿어도 돼?"

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123  # trust_level: high
lift analyze fixtures/observational_coupon.csv --estimate-propensity --seed 123  # trust_level: medium/low
lift analyze fixtures/low_overlap_coupon.csv --seed 123  # trust_level: low/blocked
```

Pass criteria:

- `trust.json`의 `trust_level` 이 randomized=high, observational=medium/low, low_overlap=low/blocked
- `warnings`에 hidden confounding 경고 포함 (observational)
- `report.md`의 Trust 섹션에 overlap_status, 경고 반영

## Q7: "관찰 데이터인데 overlap 문제는 없어?"

Test:

```bash
lift analyze fixtures/low_overlap_coupon.csv --estimate-propensity --seed 123
```

Pass criteria:

- `trust.json`의 `overlap_status = poor`
- `low_overlap_count`, `low_overlap_rate` 포함
- `propensity_percentiles` (p01, p05, p95, p99) 포함
- `trust_level = low 또는 blocked`

## Q8: "예산을 늘리면 incremental value가 얼마나 늘어나?"

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
# budget-frontier.csv에서 cumulative_expected_gain vs cumulative_expected_cost 확인
```

Pass criteria:

- `budget-frontier.csv` 존재하며 `rank`, `unit_id`, `cumulative_expected_gain`, `cumulative_expected_cost`, `cumulative_expected_roi` 포함
- LLM이 budget-frontier.csv를 읽어 예산별 incremental gain 답변 가능

**Gap:** Pi tool에 budget-frontier.csv를 직접 읽는 tool 없음. LLM이 report tool을 통해 간접 해석.

## Q9: "모델별 cost curve와 AUCC를 비교해줘."

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
# evaluation.json leaderboard에서 auuc/qini 비교
# curves.csv에서 모델별 커브 비교
```

Pass criteria:

- `curves.csv`에 모든 모델의 `incremental_gain`, `incremental_cost`, `incremental_roi`, `cpia` by `target_share` 포함
- `evaluation.json`의 leaderboard에 AUUC, Qini, gain_at_budget 포함
- 모델 간 성능 차이가 수치로 확인 가능

**Bug (v0.1.7):** `aucc`와 `auuc`가 동일한 값으로 설정됨. AUCC 수정 전까지 report에서 AUCC 항목을 AUUC(Area Under Uplift Curve)로 레이블해야 한다.

## Q10: "추천 대상자 CSV와 리포트를 만들어줘."

Test:

```bash
lift analyze fixtures/randomized_coupon.csv --budget 100000000 --seed 123
# targets.csv + report.md 생성 확인
```

Pass criteria:

- `targets.csv` 존재하며 TRD 8.2 스키마 충족
- `report.md` 존재하며 Summary, Campaign Incrementality, Budget Simulation, Trust, Model Leaderboard, Limitations 섹션 포함
- 두 파일 경로가 CLI 출력 또는 report.md 내에 명시됨

---

# 6. Core Model Test Plan

## 6.1 Duality R-learner

Test cases:

- learns `tau_gain` and `tau_cost`
- searches `lambda_grid`
- selects lambda by validation AUCC
- handles zero/negative cost effect
- supports cross-fitting

Pass criteria:

- outputs `tau_gain`, `tau_cost`, `lambda`, `score`
- selected lambda is recorded
- fixed seed produces repeatable scores
- score equals `tau_gain - lambda * tau_cost` within tolerance

## 6.2 Direct Ranking

Status: Post-MVP. MVP test runs must not require this model.

Future test cases:

- trains scoring network
- supports propensity weighting
- improves aggregate effectiveness on synthetic data
- handles mini-batch and full-batch modes
- early stopping by validation AUCC

Pass criteria:

- loss decreases or early-stops cleanly
- output scores are finite
- model artifact records architecture and seed

## 6.3 Constrained Ranking

Status: Post-MVP. MVP test runs must not require this model.

Future test cases:

- top quantile constraint
- fixed budget constraint
- minimum ROI constraint
- temperature annealing
- infeasible constraint

Pass criteria:

- hard evaluator respects final budget
- infeasible policies are marked `failed`
- selected target count does not exceed constraint

---

# 7. Integration Test Plan

## INT-001: End-to-end randomized analysis

Command:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
```

Expected artifacts:

```
run.json
schema.json
propensity.json
trust.json
campaign_incrementality.json
models.json
evaluation.json
curves.csv
budget-frontier.csv
policy-scores.csv
targets.csv
simulation.json
report.md
provenance.md
```

Pass criteria:

- all artifacts exist
- report includes Summary, Trust, Campaign Incrementality, Model Leaderboard, Budget Simulation, Limitations
- targets.csv has required export schema

## INT-002: Budget simulation

Command:

```
lift simulate <run-id> --budget 100000000 --min-roi 1.5
```

Pass criteria:

- total expected cost is <= budget
- expected iRoI is >= 1.5 when feasible
- infeasible status is explicit when not feasible

## INT-003: Observational analysis

Command:

```
lift analyze observational_coupon.csv --schema schema.yaml
```

Pass criteria:

- propensity estimation runs
- hidden confounding warning appears
- output is marked lower trust than randomized data

## INT-004: CLI/REPL parity

Commands:

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
# then in legacy REPL:
lift repl
> /analyze fixtures/randomized_coupon.csv --seed 123
```

Pass criteria:

- both invoke the same core workflow
- artifact structure is identical except run id/time

## INT-006: Install flow end-to-end

```bash
rm -rf ~/.lift ~/.local/bin/lift
LIFT_PACKAGE=. sh scripts/install/install.sh
export PATH="$HOME/.local/bin:$PATH"
lift version    # {"version": "0.1.7"}
lift doctor     # status check including node/Pi runtime
lift runtime    # available: true when node + Pi CLI installed
lift model login openai --method api-key --api-key "$OPENAI_API_KEY"
lift quickstart # end-to-end fixture run
lift            # Pi shell (if runtime available) or REPL (fallback)
```

Pass criteria:

- `lift version` returns correct version
- `lift doctor` indicates Pi runtime status (not just Python deps)
- `lift quickstart` succeeds with fixture data
- Second `lift` (no args) does NOT show model setup screen
- Pi shell (if available) responds to natural-language questions using lift tools

## INT-007: Natural-language → Lift tool chain (Pi shell)

Requires: node + @mariozechner/pi-coding-agent installed, default model configured.

Test:

```
lift
> fixtures/randomized_coupon.csv 데이터로 incremental ROI를 계산해줘.
```

Pass criteria:

- Pi shell calls `lift_inspect_dataset` or `lift_analyze_campaign` tool (not hallucinating values)
- Result includes `campaign_incrementality.json` values
- No invented metrics appear in the response
- Run id and artifact path are cited

## INT-005: Skills installer

Commands:

```
lift install-skills --target codex
lift install-skills --target repo
```

Pass criteria:

- Codex target writes `~/.codex/skills/lift/SKILL.md`
- repo target writes `.agents/skills/lift/SKILL.md`
- skill instructions call `lift doctor`, `lift quickstart`, `lift analyze`, `lift report`, and `lift export-targets`
- skill instructions tell agents to read Lift artifacts instead of inventing metrics

---

# 8. Report and Artifact QA

## 8.1 Report checks

Report must include:

- dataset summary
- schema mapping
- trust rating
- campaign-level effect
- model leaderboard
- cost curve summary
- budget recommendation
- target export path
- limitations

Report must not:

- present observational results as definitive
- invent metrics missing from artifacts
- hide failed constraints

## 8.2 Provenance checks

`provenance.md` must include:

- dataset path
- dataset fingerprint
- config
- seed
- model versions
- generated artifact list
- verification status

---

# 9. Acceptance Criteria

MVP passes when:

1. End-to-end randomized analysis passes.
2. Observational analysis emits propensity and hidden confounding warnings.
3. Low-overlap data is marked low trust or blocked.
4. Leakage columns are excluded by default.
5. Baselines and Duality R-learner all produce finite scores.
6. Cost Curve, AUCC (correctly computed against incremental_cost), iRoI, CPiA, and budget frontier are generated.
7. Budget simulation never exports a target list that violates hard budget.
8. `fractional_uplift` is not required at runtime.
9. CLI and REPL use the same core workflow.
10. Re-running with the same seed produces equivalent model/evaluation artifacts within tolerance.
11. Skills installation works for Codex user-level and repo-local targets.
12. `lift doctor` reports node/Pi CLI/OAuth bridge status (not only Python deps).
13. `policy-scores.csv` enables identification of negative-uplift customers (anti-targets).
14. Second `lift` run after successful setup skips model setup prompt.
15. `lift runtime` reports `available: true` after successful installer run on a node+npm system.

---

# 10. Known Gaps (v0.1.7)

These items are documented as failing or absent. Tests against them are expected to fail until fixed.

| ID | Gap | Severity |
|----|-----|----------|
| GAP-001 | `aucc` and `auuc` are computed identically in `metrics.py`. AUCC must be area under gain-vs-cost curve. | HIGH |
| GAP-002 | Anti-target export missing. `targets.csv` silently excludes negative-uplift customers. | HIGH |
| GAP-003 | `lift doctor` does not check node, Pi CLI, or OAuth bridge. | MEDIUM |
| GAP-004 | `/compare-models` slash command not implemented in REPL or Pi tools. | MEDIUM |
| GAP-005 | `lift status` returns `{"status": "ready"}` only, not a model/session dashboard. | MEDIUM |
| GAP-006 | OAuth provider ID mapping between Lift names and Pi AuthStorage not validated. | MEDIUM |
| GAP-007 | Optional packages multiselect in setup prints hardcoded items, does not install. | LOW |
| GAP-008 | Pi shell `--model` flag format (`provider/model`) compatibility with Pi CLI not validated. | MEDIUM |
