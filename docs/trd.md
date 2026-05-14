# TRD: Lift

## Core Models and Standalone Runtime Architecture

**문서 목적**  
이 문서는 [PRD](./prd.md)를 구현 가능한 기술 요구사항으로 분해한다. Lift의 MVP 구현 방향은 “기존 uplift 라이브러리 wrapping”이 아니라, **Baselines와 Duality R-learner를 자체 workflow로 제공하는 standalone local runtime**을 만드는 것이다. Direct Ranking과 Constrained Ranking은 Post-MVP 확장으로 둔다.

---

# 1. 기술 원칙

## 1.1 Core model ownership

Lift의 핵심 모델은 내부 구현으로 소유한다.

- baseline ranking models
- `DualityRLearner`

Post-MVP 모델:

- `DirectRankingModel`
- `ConstrainedRankingModel`

외부 라이브러리는 다음 용도로만 사용한다.

- `sklearn`: base estimator, preprocessing, metrics
- `torch`: ranking objective 학습
- `econml`: optional baseline 또는 nuisance estimator 참고
- `causalml`, `scikit-uplift`: optional baseline
- `references/fractional_uplift`: reference-only

## 1.2 Archived dependency policy

`google-marketing-solutions/fractional_uplift`는 2026-01-19에 archived/read-only가 되었으므로 필수 dependency로 사용하지 않는다.

Lift는 해당 repo에서 다음만 참고한다.

- KPI 역할 모델링
- fractional score 정의
- propensity-weighted evaluator
- distillation 아이디어
- end-to-end notebook UX

## 1.3 Local-first

- 사용자 데이터는 기본적으로 로컬에 남는다.
- 외부 API 호출은 기본 기능에 필요하지 않아야 한다.
- 모든 계산 결과는 artifact로 저장한다.

---

# 2. 시스템 아키텍처

## 2.1 계층 구조

1. **Interface Layer**
   - CLI
   - REPL slash command
   - setup/quickstart commands
   - skills/prompts installer for Codex/Claude

2. **Workflow Layer**
   - run orchestration
   - step state
   - artifact registry
   - provenance logging

3. **Data Layer**
   - CSV/Parquet loading
   - schema mapping
   - data validation
   - train/validation/test split
   - cross-fitting split

4. **Causal Trust Layer**
   - randomized/observational 판단
   - propensity handling
   - overlap diagnostics
   - covariate balance
   - leakage detection
   - trust rating

5. **Model Layer**
   - baseline estimators
   - Duality R-learner

6. **Evaluation Layer**
   - campaign-level incrementality
   - cost curve
   - AUCC
   - iRoI
   - CPiA
   - budget frontier

7. **Decision Layer**
   - budget-constrained targeting
   - ROI-constrained targeting
   - target export
   - report generation

---

# 3. Data Contract

## 3.1 Logical schema

Required:

```
unit_id: string
treatment: binary int
maximize_kpi: numeric
constraint_kpi: numeric
features: table columns
```

Required or inferred:

```
treatment_propensity: float in (0, 1)
```

Optional:

```
constraint_offset_kpi: numeric
constraint_offset_scale: float
sample_weight: numeric
campaign_id: string
treatment_timestamp: datetime
outcome_window_start: datetime
outcome_window_end: datetime
```

## 3.2 MVP assumptions

- `treatment`는 binary만 지원한다.
- 한 row는 한 user-treatment decision unit이다.
- 모든 feature는 treatment 이전 시점에 관측되어야 한다.
- `maximize_kpi`와 `constraint_kpi`는 같은 outcome window에서 측정되어야 한다.

---

# 4. Causal Trust Layer

## 4.1 Diagnostics

필수 진단:

- treatment/control 존재 여부
- treatment ratio
- treatment/control sample size
- propensity source
- propensity min/max/percentile
- overlap risk
- covariate balance
- leakage candidate
- post-treatment feature candidate
- hidden confounding warning

## 4.2 Trust rating

출력은 다음 등급을 사용한다.

```
high
medium
low
blocked
```

`blocked` 조건:

- treatment 또는 control이 없음
- propensity가 0 또는 1인 구간이 과도함
- 필수 KPI 누락
- obvious post-treatment leakage가 핵심 feature에 포함됨

---

# 5. Model Specifications

## 5.1 Baseline models

Baseline은 core model의 비교 기준이다.

- Random ranking
- Response model
- T-learner for maximize KPI
- T-learner for constraint KPI
- Profit ranking baseline

Baseline은 Lift의 차별점이 아니므로 dependency를 optional로 유지할 수 있다.

## 5.2 Duality R-learner

목적:

- gain과 cost의 treatment effect를 분리 또는 결합 추정한다.
- Lagrangian multiplier로 budget/cost trade-off를 반영한다.

Required inputs:

```
X
treatment
maximize_kpi
constraint_kpi
treatment_propensity
lambda_grid
```

Core score:

```
score_i = tau_gain(x_i) - lambda * tau_cost(x_i)
```

Implementation requirements:

- nuisance outcome model `m(x)` 지원
- propensity model `e(x)` 지원
- cross-fitting 지원
- `lambda`는 validation AUCC 또는 policy value 기준으로 선택
- `tau_cost <= 0` 또는 unstable denominator 상황에 대한 guardrail 필요

Output:

```
tau_gain
tau_cost
lambda
score
selected_lambda_metric
```

## 5.3 Direct Ranking

Status: Post-MVP.

목적:

- 개별 CATE point estimate를 먼저 맞추는 대신, score가 만든 cohort의 aggregate effectiveness를 직접 최적화한다.

Required inputs:

```
X
treatment
maximize_kpi
constraint_kpi
treatment_propensity
sample_weight
```

Model:

```
score_i = f_theta(x_i)
```

Training objective:

- treatment/control group별 score-normalized weighting
- propensity weighting
- aggregate incremental gain
- aggregate incremental cost
- ratio 또는 negative effectiveness loss

Implementation requirements:

- PyTorch backend
- deterministic seed
- mini-batch와 full-batch mode
- gradient clipping
- numerical stability guards
- validation AUCC early stopping

## 5.4 Constrained Ranking

Status: Post-MVP.

목적:

- Direct Ranking objective에 target ratio, fixed budget, minimum ROI 같은 제약을 반영한다.

Supported constraints:

```
max_target_ratio
budget
min_roi
top_quantile
```

Mechanisms:

- quantile thresholding
- budget thresholding by cumulative expected cost
- sigmoid fall-off
- temperature annealing

Implementation requirements:

- hard selection evaluator와 soft training objective를 분리한다.
- training 시 constraint relaxation을 사용하더라도 evaluation은 실제 budget/ROI 기준으로 계산한다.
- 제약을 만족하지 못하면 `constraint_status=failed`를 반환한다.

---

# 6. Fractional Objective

Lift는 fractional uplift package를 dependency로 쓰지 않지만, 내부 objective API는 다음 구조를 지원한다.

```
maximize_kpi = alpha
constraint_kpi = beta
constraint_offset_kpi = gamma
constraint_offset_scale = delta
```

Reference score:

```
fractional_score =
  CATE(alpha) / (CATE(beta) - CATE(gamma) / delta)
```

Requirements:

- denominator near-zero guard
- infinity score handling
- negative denominator policy
- optional distillation target generation

이 objective는 core model의 보조 scoring mode로 쓰며, MVP 핵심 모델은 Baselines와 Duality R-learner다.

---

# 7. Evaluation

## 7.1 Campaign-level incrementality

모델 학습 전 전체 캠페인 효과를 먼저 계산한다.

Required metrics:

- incremental maximize KPI
- incremental constraint KPI
- incremental offset KPI
- incremental ROI
- confidence interval for randomized experiment

## 7.2 Ranking evaluation

Required curves:

- incremental gain vs share targeted
- incremental gain vs incremental cost
- iRoI vs incremental gain
- CPiA vs incremental acquisition
- cost curve

Required scalar metrics:

- AUCC
- AUUC
- Qini
- iRoI at budget
- gain at min ROI
- max gain under budget
- target count at cutoff

## 7.3 Propensity weighting

Evaluator는 ATE/ATT/ATC 모드를 지원해야 한다.

MVP default:

```
effect_type = ATE
```

ATE weights:

```
treatment rows: 1 / propensity
control rows: 1 / (1 - propensity)
```

---

# 8. Policy Optimization

## 8.1 Selection policies

Supported policies:

- top-k by score
- top share by score
- max gain under budget
- max gain with min ROI
- max profit under budget

## 8.2 Target export schema

`targets.csv` must include:

```
unit_id
rank
score
recommended_treatment
expected_incremental_gain
expected_incremental_cost
expected_incremental_profit
expected_incremental_roi
selection_reason
trust_level
```

---

# 9. Standalone Runtime Contract

## 9.1 CLI commands

```
lift
lift chat [prompt]
lift setup
lift quickstart
lift inspect <dataset>
lift analyze <dataset>
lift simulate <run-id>
lift export-targets <run-id>
lift report <run-id>
lift outputs
lift doctor
lift status
```

## 9.2 REPL slash commands

```
/inspect <dataset>
/validate
/analyze <objective>
/compare-models
/simulate budget=<number> min_roi=<number>
/export-targets
/report
/outputs
```

## 9.3 Install and setup commands

Required:

```
curl -fsSL <install-url> | bash
lift setup
lift doctor
lift quickstart
lift install-skills --target codex
lift install-skills --target repo
```

The standalone runtime must not require MCP. Agent integrations are delivered through skills/prompts that call the local `lift` CLI and read artifacts.

---

# 10. Artifact Contract

Each run writes:

```
outputs/<slug>/run.json
outputs/<slug>/schema.json
outputs/<slug>/trust.json
outputs/<slug>/campaign_incrementality.json
outputs/<slug>/models.json
outputs/<slug>/evaluation.json
outputs/<slug>/budget-frontier.csv
outputs/<slug>/targets.csv
outputs/<slug>/report.md
outputs/<slug>/provenance.md
```

`run.json` must include:

```
seed
created_at
dataset_fingerprint
model_versions
config
status
```

`provenance.md` must include:

- input dataset path and fingerprint
- user-provided schema mapping
- generated artifacts
- verification status
- warnings that affect interpretation

---

# 11. Implementation Phases

## Phase 1: Evaluation and Trust Foundation

- schema mapping
- Causal Trust Layer
- campaign-level incrementality
- cost curve evaluator
- AUCC/iRoI/CPiA
- target export
- report generation

## Phase 2: Core Models

- baseline ranking models
- Duality R-learner
- model leaderboard
- budget simulation

## Phase 3: Standalone UX

- CLI commands
- REPL slash commands
- setup command
- one-line installer
- skills/prompts installer
- output browser
- doctor/status

## Phase 4: Extensions

- optional baseline adapters
- Direct Ranking
- Constrained Ranking
- model distillation
- multi-treatment
- bucketized continuous treatment
- local preview

---

# 12. Completion Criteria

MVP is complete when:

1. Core workflow runs without `fractional_uplift` as a dependency.
2. Baselines and Duality R-learner produce comparable score columns.
3. Evaluation computes Cost Curve, AUCC, iRoI, CPiA, and budget frontier.
4. Budget simulation never exports targets above the configured budget.
5. Trust Layer blocks invalid datasets and warns on observational risk.
6. CLI and REPL use the same core engine.
7. Every run writes reproducible artifacts and provenance.
8. Codex/Claude integration is available through skills/prompts, not MCP.
