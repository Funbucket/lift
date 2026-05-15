# PRD: Lift

## Feynman식 Local Incrementality Decision Runtime

---

# 1. 제품명

**Lift**

---

# 2. 제품 한 줄 설명

**Lift는 실험 데이터 또는 신뢰 가능한 관찰 데이터를 기반으로, 캠페인의 incremental value와 incremental cost를 함께 학습해 예산/ROI 제약 하에서 최적의 타겟팅 정책을 추천하는 로컬 오픈소스 분석 에이전트다.**

---

# 3. 제품 비전

마케팅/CRM/커머스 팀은 캠페인 성과를 볼 때 전환율, 매출, 클릭률, 구매 확률을 자주 사용한다. 하지만 이런 지표는 “원래 구매했을 고객”과 “캠페인 때문에 추가로 구매한 고객”을 구분하지 못한다.

Lift의 목표는 다음 질문에 답하는 것이다.

> “이 캠페인은 실제로 얼마만큼의 incremental value를 만들었고, 어떤 고객에게 처치해야 예산 효율이 가장 높은가?”

제품의 핵심은 단순 CATE 추정이 아니라 **cost-aware incrementality decision**이다. Lift는 개별 고객의 uplift score를 보여주는 데서 멈추지 않고, 캠페인 전체의 portfolio effectiveness를 최적화해야 한다.

---

# 4. 핵심 이론 기준

Lift의 모델 설계는 다음 reference를 기준으로 한다.

- `references/paper_2004_09702/2004.md`
- `references/fractional_uplift/`
- `references/feynman/`

## 4.1 핵심 모델

이번 MVP의 1급 모델은 다음 두 계열이다.

1. **Baselines**
   - random ranking, response model, T-learner, profit ranking을 비교 기준으로 제공한다.
   - 제품 차별점이 아니라 sanity check와 leaderboard 기준 역할을 한다.

2. **Duality R-learner**
   - gain CATE와 cost CATE를 각각 또는 결합 형태로 추정한다.
   - 예산 제약을 Lagrangian multiplier로 반영한다.
   - ranking score는 기본적으로 `tau_gain(x) - lambda * tau_cost(x)` 계열이어야 한다.

Post-MVP 후보:

1. **Direct Ranking**
   - CATE point estimate의 정확도보다 aggregate portfolio effectiveness를 직접 최적화한다.
   - score function `f(x)`를 학습하고, score 기반 cohort의 incremental gain/cost ratio를 objective로 둔다.

2. **Constrained Ranking**
   - Direct Ranking에 quantile 또는 budget constraint를 직접 반영한다.
   - top quantile, fixed budget, ROI threshold 같은 제약을 soft constraint 또는 annealing으로 학습한다.

## 4.2 Fractional Uplift의 위치

`references/fractional_uplift`는 참고 구현이다. 해당 upstream repository는 **2026-01-19에 archived/read-only 상태가 되었으므로**, Lift의 필수 runtime dependency로 사용하지 않는다.

Lift는 fractional uplift의 다음 개념을 제품 설계에 반영한다.

- `maximize_kpi`
- `constraint_kpi`
- `constraint_offset_kpi`
- `constraint_offset_scale`
- iRoI, CPiA, incremental metric curve
- meta learner distillation 아이디어

하지만 core objective, evaluator, model training은 Lift 내부 구현으로 유지한다.

---

# 5. 문제 정의

## 5.1 Response prediction의 한계

구매 확률이 높은 고객을 찾는 모델은 “개입해야 할 고객”이 아니라 “원래 살 가능성이 높은 고객”을 고를 수 있다.

캠페인 의사결정의 질문은 다음이다.

```
누가 구매할 것인가?
```

가 아니라:

```
누구에게 개입해야 추가 가치가 발생하는가?
```

## 5.2 단일 KPI uplift의 한계

regular uplift modeling은 보통 단일 outcome의 CATE를 추정한다. 그러나 쿠폰, 할인, 리워드 캠페인에서는 treatment cost가 고객별로 다르고, 비용이 실제 구매 여부에 따라 발생할 수도 있다.

따라서 Lift는 다음을 함께 다뤄야 한다.

- incremental gain
- incremental cost
- incremental profit
- incremental ROI
- cost per incremental acquisition
- budget-constrained policy value

## 5.3 CATE와 정책 실행의 단절

기존 causal/uplift 도구는 보통 고객별 treatment effect 추정에서 멈춘다. Lift는 다음 질문까지 답해야 한다.

- 예산 1억이면 누구에게 보내야 하는가?
- ROI 1.5 이상을 유지하려면 어디까지 타겟팅해야 하는가?
- incremental conversion을 최대화하면서 iRoI 2.0을 지킬 수 있는가?
- 단순 uplift model과 cost-aware model은 얼마나 다른 cohort를 추천하는가?

## 5.4 인과추론 가정 검증의 어려움

관찰 데이터에서는 다음 문제가 발생할 수 있다.

- treatment propensity 문제
- overlap 부족
- hidden confounding
- post-treatment variable 사용
- leakage
- treatment/control imbalance

Lift는 모델 학습뿐 아니라 **Causal Trust Layer**를 제품의 핵심 기능으로 제공해야 한다.

## 5.5 오픈소스 도구의 UX 문제

CausalML, EconML, scikit-uplift, fractional uplift 계열 라이브러리는 유용하지만, 실무자가 end-to-end workflow를 직접 구성하기 어렵다.

Lift는 다음 과정을 Feynman 스타일의 로컬 agent workflow로 묶는다.

```
데이터 점검
→ 인과 가정 진단
→ 전체 캠페인 incrementality 분석
→ cost-aware 모델 학습
→ cost curve / AUCC 평가
→ 예산/ROI 시뮬레이션
→ 대상자 리스트 export
→ 검증 가능한 리포트 생성
```

---

# 6. 제품 목표

사용자가 다음처럼 요청하면:

> “이 쿠폰 캠페인 데이터로 예산 1억 기준 타겟팅 정책을 추천해줘. ROI는 1.5 이상이면 좋겠어.”

Lift는 다음 결과를 자동 생성해야 한다.

1. 데이터 스키마 점검
2. treatment, KPI, cost, covariate 확인
3. 실험 데이터/관찰 데이터 여부 판단
4. propensity 및 overlap 진단
5. 전체 캠페인 incremental ROI 분석
6. Duality R-learner 학습
7. baseline 모델과 cost-aware 모델 비교
8. Cost Curve, AUCC, iRoI, CPiA 계산
9. 예산별 target count와 expected value 계산
10. 대상자 리스트 export
11. 리포트와 provenance artifact 생성

---

# 7. 제품 범위

## 7.1 MVP 포함 범위

- 단일 캠페인 분석
- binary treatment
- randomized experiment 우선
- 관찰 데이터는 trust warning과 함께 지원
- multi-KPI objective
- customer-level target ranking
- budget / ROI / target-ratio constraint
- local CLI
- Feynman-style local terminal app launched by `lift`
- local REPL with slash workflows
- `lift model ...` model/auth configuration surface
- `lift agent ...` Codex/Claude integration surface
- one-line installer
- Codex/Claude용 skills/prompts 설치 산출물
- Markdown/JSON/CSV artifact

## 7.2 MVP 제외 범위

- multi-treatment 정식 최적화
- continuous treatment 정식 dose-response
- 온라인 실시간 serving
- 자동 캠페인 집행
- 외부 warehouse 직접 연결
- MCP server interface
- direct MCP-based agent runtime
- 의료/금융/채용/정치 등 고위험 의사결정

## 7.4 Feynman-style runtime expectations

Lift should install and run like a standalone local app:

```bash
curl -fsSL <install-url> | bash
lift
```

Running `lift` without arguments must behave like Feynman's first-run CLI. If no default model is configured, the first screen must be the Feynman-style model setup flow with arrow-key selection. After model setup completes, or on later runs where a model is already configured, `lift` should show a terminal dashboard with runtime status, configured model, working directory, output location, available agent integrations, and Lift slash workflows.

Model/account access is split into three modes:

- OAuth provider login through a Pi-compatible auth bridge
- API-key provider setup for OpenAI, Anthropic, Google, and compatible gateways
- External CLI integration for already-authenticated Codex or Claude installations

Lift must not claim OAuth credentials are available unless the OAuth bridge has completed a real provider login.

## 7.5 Feynman UX implementation source

Lift UX must be implemented by referencing the cloned Feynman source code under `references/feynman`, not by inventing a separate interaction model.

Required reference files:

- `references/feynman/src/setup/prompts.ts`
  - wraps `@clack/prompts`
  - provides direction-key `select`, checkbox-style `multiselect`, `text`, `confirm`, `intro`, and `outro`
  - Lift setup UX must match this interaction model rather than numeric-only prompts
- `references/feynman/src/model/commands.ts`
  - `runModelSetup()` defines the model access flow:
    - OAuth login
    - API key or custom provider
    - Cancel
  - `loginModelProvider()` defines browser OAuth behavior through `AuthStorage.login()`
  - Lift model setup must follow this sequence and wording unless there is a product-specific reason documented in PRD/TRD
- `references/feynman/src/setup/setup.ts`
  - defines full setup progression after model auth
  - Lift should mirror the staged setup style: model auth, package status, optional packages, ready summary

Implementation requirement:

- Do not hand-roll terminal selection UX in Python when the target is Feynman parity.
- Use a Node setup/auth helper with `@clack/prompts`, or another implementation that demonstrably matches Feynman's `@clack/prompts` behavior.
- The user must be able to move choices with arrow keys, confirm with Enter, and see selected prompts collapse from active `◆` to completed `◇` sections.
- OAuth login should open the browser automatically and continue when the callback completes; manual paste of redirect URL/auth code should appear only when the provider bridge requests it.
- The setup screen must not require users to copy the `Auth URL` manually when the browser callback flow succeeds.

## 7.3 Post-MVP 후보

- multi-treatment allocation
- bucketized continuous treatment
- policy tree / rule extraction 고도화
- model distillation
- Direct Ranking
- Constrained Ranking
- notebook integration
- local web preview

---

# 8. 초기 타겟 사용자

## 8.1 Primary Users

### 데이터 사이언티스트

- uplift 모델 성능 체크
- campaign incrementality 평가
- cost-aware policy learning
- model leaderboard 검토

### ML 엔지니어

- 로컬 분석 파이프라인 구성
- CLI/REPL 기반 자동화
- Codex/Claude skills 기반 분석 보조
- 모델 artifact/export 구성
- custom estimator 연결

### CRM / Growth / Marketing Analyst

- 누구에게 쿠폰을 줄지 결정
- 캠페인이 실제로 돈을 벌었는지 확인
- 예산별 ROI를 비교
- 다음 캠페인 타겟 리스트 생성

## 8.2 사용자 수준

초기 제품은 **uplift와 실험 분석을 어느 정도 이해하는 실무자**를 기준으로 한다.

완전 비전문가용 AutoML이 아니라, 전문가가 검토 가능한 agentic workflow를 제공한다.

---

# 9. 초기 Vertical

## 9.1 1차 Vertical

### CRM 쿠폰 / 프로모션 최적화

- 쿠폰 지급 여부
- 할인율 제공 여부
- 무료배송 제공 여부
- 포인트 지급 여부
- 멤버십 혜택 제공 여부

### 커머스 개인화 마케팅

- 고객별 프로모션 타겟팅
- 장바구니 이탈 고객 리마인드
- 재구매 유도 캠페인
- VIP 고객 혜택 최적화

## 9.2 제외 Vertical

- 의료 intervention
- 금융 대출 승인
- 보험 underwriting
- 채용/인사 의사결정
- 정치 캠페인 타겟팅
- 법적 권리나 필수 서비스 접근에 영향을 주는 정책

---

# 10. KPI 설계

Lift는 단일 `outcome`이 아니라 다음 KPI 역할을 명시적으로 받는다.

## 10.1 Maximize KPI

최대화할 incremental value.

예:

- conversion
- revenue
- gross profit
- retention
- purchase amount
- LTV proxy

## 10.2 Constraint KPI

낮게 유지해야 할 비용 또는 제약.

예:

- coupon cost
- discount cost
- reward cost
- marketing spend
- support cost

## 10.3 Constraint Offset KPI

constraint를 상쇄하는 value.

예:

- revenue
- margin
- incremental spend
- future value

## 10.4 Constraint Offset Scale

offset KPI를 constraint 기준으로 환산하는 값.

예:

- target iRoI = 2.0
- target payback ratio = 1.5
- margin conversion factor

---

# 11. 데이터 계약

## 11.1 표준 입력 포맷

초기 버전은 한 row가 한 user-treatment decision unit을 의미한다.

필수 논리 필드:

```
unit_id
treatment
treatment_propensity
maximize_kpi
constraint_kpi
feature_1
...
feature_n
```

선택 논리 필드:

```
constraint_offset_kpi
sample_weight
campaign_id
treatment_timestamp
outcome_window_start
outcome_window_end
```

## 11.2 실험 데이터

- `treatment`는 0/1이어야 한다.
- `treatment_propensity`가 없으면 traffic split 또는 treatment 비율로 생성 가능하다.
- feature는 treatment 이전에 관측된 값이어야 한다.

## 11.3 관찰 데이터

- propensity를 추정할 수 있는 pre-treatment covariate가 필요하다.
- cross-fitting 기반 propensity estimation을 사용해야 한다.
- hidden confounding risk를 항상 명시한다.

---

# 12. 핵심 사용자 질문

Lift는 아래 질문에 직접 답할 수 있어야 한다.

1. “이 캠페인의 incremental ROI는 얼마야?”
2. “예산 1억이면 누구에게 쿠폰을 보내야 해?”
3. “iRoI 2.0을 유지하면서 incremental conversion을 최대화해줘.”
4. “단순 uplift 모델과 cost-aware 모델의 추천 대상은 얼마나 달라?”
5. “쿠폰이 손해인 고객군은 누구야?”
6. “이 데이터로 인과추론 결과를 믿어도 돼?”
7. “관찰 데이터인데 overlap 문제는 없어?”
8. “예산을 늘리면 incremental value가 얼마나 늘어나?”
9. “모델별 cost curve와 AUCC를 비교해줘.”
10. “추천 대상자 CSV와 리포트를 만들어줘.”

---

# 13. UX 요구사항

최종 UX는 Feynman 느낌을 따른다.

## 13.1 CLI

Core commands:

```
lift
lift chat [prompt]
lift setup
lift quickstart
lift analyze <dataset>
lift simulate <run-id>
lift report <run-id>
lift outputs
lift doctor
lift status
```

Flags:

```
--cwd <path>
--session-dir <path>
--config <path>
--new-session
--seed <int>
--dry-run
```

## 13.2 REPL slash workflow

```
/inspect data.csv
/validate
/analyze incremental ROI
/compare-models
/simulate budget=100000000 min_roi=1.5
/export-targets
/report
/outputs
```

## 13.3 Output style

- 결과는 숫자, chart artifact, warning, recommendation을 함께 제공한다.
- 계산값은 tool output에서 온 값만 사용한다.
- low-trust 분석은 “확정적 추천”처럼 표현하지 않는다.
- 모든 run은 재현 가능한 artifact를 남긴다.

## 13.4 Agent integration

Codex/Claude 연동은 MCP 서버가 아니라 Feynman식 skills/prompts 설치를 기준으로 한다.

- Codex user-level: `~/.codex/skills/lift`
- repo-local agent: `.agents/skills/lift`
- skill은 `lift doctor`, `lift quickstart`, `lift analyze`, `lift report`, `lift export-targets` 사용법을 안내한다.
- agent는 계산을 직접 추정하지 않고 Lift artifact를 읽어 설명한다.

---

# 14. 산출물

Lift run은 다음 artifact를 생성해야 한다.

```
outputs/<slug>/run.json
outputs/<slug>/schema.json
outputs/<slug>/trust.json
outputs/<slug>/models.json
outputs/<slug>/evaluation.json
outputs/<slug>/budget-frontier.csv
outputs/<slug>/targets.csv
outputs/<slug>/report.md
outputs/<slug>/provenance.md
```

---

# 15. 성공 기준

MVP는 다음을 만족하면 된다.

1. randomized binary campaign 데이터에서 end-to-end 분석을 완료한다.
2. Baselines와 Duality R-learner를 core model로 실행한다.
3. Cost Curve, AUCC, iRoI, CPiA를 계산한다.
4. 예산/ROI 제약을 만족하는 target list를 생성한다.
5. Causal Trust Layer가 leakage, overlap, hidden confounding risk를 보고한다.
6. `fractional_uplift` 없이도 core workflow가 동작한다.
7. Feynman식 standalone CLI/REPL workflow와 artifact 출력 규칙을 제공한다.
8. Codex/Claude용 Lift skills/prompts 설치 산출물을 제공한다.
