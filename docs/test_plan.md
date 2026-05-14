# Lift Test Plan

## Core Model, Evaluation, UX, and Trust Validation

---

# 1. Purpose

이 문서는 Lift가 PRD/TRD의 핵심 요구사항을 만족하는지 검증하기 위한 테스트 계획이다. 테스트의 중심은 다음이다.

- `fractional_uplift` 없이 core workflow가 동작하는가
- Duality R-learner, Direct Ranking, Constrained Ranking이 실행되는가
- Cost Curve, AUCC, iRoI, CPiA가 정확하게 계산되는가
- 예산/ROI 제약을 위반하지 않는 target list가 생성되는가
- Feynman식 CLI/REPL/MCP UX가 같은 core engine을 사용하는가

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
- CLI, REPL, MCP smoke tests

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

Test cases:

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

Test cases:

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

```
lift analyze randomized_binary_coupon.csv --seed 123
```

Expected artifacts:

```
run.json
schema.json
trust.json
campaign_incrementality.json
models.json
evaluation.json
budget-frontier.csv
targets.csv
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

```
lift analyze data.csv
lift
> /analyze data.csv
```

Pass criteria:

- both invoke the same core workflow
- artifact structure is identical except run id/time

## INT-005: MCP parity

MCP calls:

```
inspect_dataset
validate_causal_assumptions
train_duality_r_learner
train_direct_ranking
train_constrained_ranking
evaluate_rankings
simulate_budget
generate_report
```

Pass criteria:

- MCP outputs match CLI workflow outputs for the same config

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
5. Duality R-learner, Direct Ranking, and Constrained Ranking all produce finite scores.
6. Cost Curve, AUCC, iRoI, CPiA, and budget frontier are generated.
7. Budget simulation never exports a target list that violates hard budget.
8. `fractional_uplift` is not required at runtime.
9. CLI, REPL, and MCP use the same core workflow.
10. Re-running with the same seed produces equivalent model/evaluation artifacts within tolerance.

