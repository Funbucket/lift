# Lift 구현 계획 및 검증 절차

> 작성 기준: v0.1.7 코드 점검 결과 (2026-05-16)

---

## 1. 현재 상태 요약

### 완료된 것

| 항목 | 파일 |
|------|------|
| `lift analyze` 전체 파이프라인 | `src/lift/workflow/run.py` |
| Baselines + Duality R-learner | `src/lift/models/` |
| 14개 artifact 생성 | `src/lift/workflow/artifacts.py` |
| Trust diagnostics (overlap, leakage, balance) | `src/lift/trust/diagnostics.py` |
| Campaign-level iROI, CI, CPiA | `src/lift/evaluation/metrics.py` |
| Budget frontier, simulate, export-targets | `src/lift/workflow/simulate.py` |
| Legacy slash-command REPL | `src/lift/interfaces/repl.py` |
| Feynman 대시보드 (ASCII panel) | `src/lift/interfaces/terminal.py` |
| `lift model/agent` 명령 그룹 | `src/lift/interfaces/cli.py` |
| setup_prompt.mjs (@clack/prompts, arrow-key 선택) | `src/lift/oauth/setup_prompt.mjs` |
| pi_auth_bridge.mjs (AuthStorage.login, browser open) | `src/lift/oauth/pi_auth_bridge.mjs` |
| lift_tools.mjs (5 Pi tools) | `src/lift/pi_assets/lift_tools.mjs` |
| install.sh + OAuth bridge npm install | `scripts/install/install.sh` |
| First-run setup 후 재실행 시 setup 스킵 | settings.json 체크 in cli.py |
| install-skills (codex/repo) | `src/lift/system/skills.py` |

### 부분 구현 (동작하지만 제한 있음)

| 항목 | 제한 |
|------|------|
| Pi 자연어 shell | node + `@mariozechner/pi-coding-agent` 필요. 없으면 REPL fallback |
| OAuth browser login | Lift provider ID ↔ Pi AuthStorage 매핑 미검증 |
| iROI 제약 최대화 | greedy 근사, 전역 최적 아님 |
| setup optional packages UI | 하드코딩 print, 실제 설치 안 됨 |

### 미구현 / 버그

| 항목 | 위치 | 심각도 |
|------|------|--------|
| AUCC = AUUC 버그 | `metrics.py:47-48` | 🔴 |
| Anti-target export (negative uplift 고객) | `metrics.py:152` | 🔴 |
| `lift doctor` Pi runtime 미체크 | `system/doctor.py` | 🟠 |
| `/compare-models` tool 미구현 | REPL + Pi tools | 🟠 |
| `lift status` trivial | `cli.py:287` | 🟠 |
| OAuth provider ID 매핑 미검증 | `pi_auth_bridge.mjs:61` | 🟠 |

### Feynman UX 대비 차이

| Feynman 동작 | Lift 현재 | 사용자 관점 문제 |
|---|---|---|
| doctor가 node/패키지 상태까지 보고 | Python만 체크 | 자연어 shell이 왜 안 되는지 알 수 없음 |
| setup 이후 optional packages 실제 선택·설치 | 하드코딩 print | 사용자가 뭔가 선택하는 것처럼 보이지만 아무것도 안 됨 |
| `feynman status` → 사람이 읽을 수 있는 요약 | `{"status":"ready"}` JSON | 현재 모델/세션/outputs 상태를 한눈에 파악 불가 |

---

## 2. 구현 계획 (우선순위 순)

### P0 — 테스트 자체가 의미없는 blockers

#### P0-A: `lift doctor`에 Pi runtime 체크 추가
- **수정 파일:** `src/lift/system/doctor.py`
- **완료 기준:** `lift doctor` 출력에 node, pi_cli, oauth_bridge, setup_prompt 각각의 available 포함. Pi 미설치 시 `status: warning`
- **테스트:**
  ```bash
  lift doctor  # node/pi_cli/oauth_bridge 필드 확인
  ```

#### P0-B: AUCC 버그 수정
- **수정 파일:** `src/lift/evaluation/metrics.py`
- **현재:** `aucc = auuc` (둘 다 gain vs target_share)
- **수정:** `aucc = _area_under_curve(curve, "incremental_cost", "incremental_gain")`
- **테스트:**
  ```bash
  lift analyze fixtures/randomized_coupon.csv --seed 123
  # evaluation.json에서 aucc != auuc 확인
  ```

#### P0-C: npm 패키지 접근성 확인 (수동)
```bash
npm view @mariozechner/pi-coding-agent version
```

---

### P1 — Pi shell 기능 보강

#### P1-A: Anti-target export (negative uplift 고객군)
- **수정 파일:** `evaluation/metrics.py`, `workflow/run.py`, `workflow/report.py`
- **완료 기준:** `anti-targets.csv` artifact 생성. `report.md`에 do-not-treat 섹션 추가
- **테스트:**
  ```bash
  lift analyze fixtures/randomized_coupon.csv --seed 123
  ls ~/.lift/outputs/*/anti-targets.csv
  ```

#### P1-B: Pi tools에 `lift_compare_models` 추가
- **수정 파일:** `src/lift/pi_assets/lift_tools.mjs`
- **완료 기준:** Pi shell에서 "모델 비교" 질문 시 evaluation.json + curves.csv 기반 답변

#### P1-C: Pi tools에 `lift_budget_frontier` 추가
- **수정 파일:** `src/lift/pi_assets/lift_tools.mjs`
- **완료 기준:** Pi shell에서 "예산을 늘리면" 질문 시 budget-frontier.csv 기반 답변

---

### P2 — UX 보강

#### P2-A: `lift doctor` 사람이 읽을 수 있는 출력
- `lift doctor` (TTY) → 체크리스트. `lift doctor --json` → JSON

#### P2-B: `lift status` 대시보드화
- 현재 모델, output root, 최신 run, Pi runtime 상태

#### P2-C: `lift quickstart` 개선
- 종료 시 `lift report <run-id>` 안내 출력

---

## 3. 직접 테스트 절차

### 3-1. 기존 설치 완전 제거

```bash
rm -rf ~/.lift
rm -f ~/.local/bin/lift
which lift  # 출력 없어야 함
```

### 3-2. 설치

```bash
cd /Users/hc.cho/Projects/lift
LIFT_PACKAGE=. sh scripts/install/install.sh
export PATH="$HOME/.local/bin:$PATH"
```

### 3-3. 설치 확인

```bash
lift version       # {"version": "0.1.8"}
lift runtime       # available: true/false
lift doctor        # node/pi_cli/oauth_bridge 상태 포함 (v0.1.8+)
```

### 3-4. 모델 설정

```bash
# API key 방식
lift model login openai --method api-key --api-key "$OPENAI_API_KEY"
lift model list    # current: "openai/gpt-4o"

# OAuth 방식 (Pi bridge 필요)
lift setup
```

### 3-5. `lift` 실행

```bash
lift
# Pi shell 가능 → 자연어 prompt
# Pi shell 불가 → "Natural-language runtime unavailable..." + legacy REPL
```

### 3-6. Quickstart

```bash
lift quickstart
# 종료 후 run_id와 report 명령 출력됨 (v0.1.8+)
```

### 3-7. 핵심 fixture 분석

```bash
lift analyze fixtures/randomized_coupon.csv --seed 123
RUN=$(ls -t ~/.lift/outputs/ | head -1)

# Artifacts 확인
ls ~/.lift/outputs/$RUN/  # 14개 파일 + anti-targets.csv (v0.1.8+)

# iROI 확인
python3 -c "
import json
d = json.load(open(f'$HOME/.lift/outputs/$RUN/campaign_incrementality.json'))
print('Campaign iROI:', d['incremental_roi'])
"

# Trust 확인
python3 -c "
import json
d = json.load(open(f'$HOME/.lift/outputs/$RUN/trust.json'))
print('Trust:', d['trust_level'], '| Overlap:', d['overlap_status'])
"
```

### 3-8. 핵심 질문 CLI 테스트

```bash
# Q1: iROI
cat ~/.lift/outputs/$RUN/campaign_incrementality.json | python3 -m json.tool

# Q2: 예산 타겟팅
lift simulate "$RUN" --budget 100000000 --min-roi 1.5
wc -l ~/.lift/outputs/$RUN/targets.csv

# Q3: iROI 제약
lift simulate "$RUN" --min-roi 2.0

# Q5: 손해 고객군 (v0.1.8+)
ls ~/.lift/outputs/$RUN/anti-targets.csv
wc -l ~/.lift/outputs/$RUN/anti-targets.csv

# Q8: budget frontier
head -10 ~/.lift/outputs/$RUN/budget-frontier.csv

# Q9: 모델 비교 (AUCC 수정 후)
python3 -c "
import json
d = json.load(open(f'$HOME/.lift/outputs/$RUN/evaluation.json'))
for r in d['leaderboard']: print(r['model'], 'auuc:', round(r['auuc'],4), 'qini:', round(r['qini'],4))
"

# Q10: report
lift report "$RUN"
```

### 3-9. 재실행 시 setup 반복 여부 확인

```bash
lift model list | grep '"current"'  # "openai/gpt-4o"
lift  # setup 화면 없이 바로 Pi shell (또는 REPL) 진입
```

### 3-10. 실패 시 확인할 파일

```bash
cat ~/.lift/settings.json
cat ~/.lift/auth.json
ls ~/.lift/oauth-bridge/node_modules/@mariozechner/ 2>&1
ls ~/.lift/oauth-bridge/node_modules/@clack/ 2>&1
~/.lift/venv/bin/pip show lift-agent
```

---

## 4. 핵심 사용자 질문 테스트 매트릭스

| # | 질문 | 필요 데이터 | 내부 tool/CLI | 기대 산출물 | 현재 | 필요 작업 |
|---|------|-----------|--------------|------------|------|----------|
| Q1 | "이 캠페인의 incremental ROI는 얼마야?" | unit_id, treatment, treatment_propensity, maximize_kpi, constraint_kpi, feature_* | `lift_analyze_campaign` | `campaign_incrementality.json`의 `incremental_roi` | ✅ | — |
| Q2 | "예산 1억이면 누구에게 쿠폰을 보내야 해?" | 동일 | `lift_analyze_campaign(budget=1e8)` + `lift_export_targets` | targets.csv (budget 적용) | ✅ | greedy 한계 명시 |
| Q3 | "iRoI 2.0을 유지하면서 incremental conversion을 최대화해줘." | 동일 | `lift_simulate_policy(min_roi=2.0)` | targets.csv, simulation.json | ⚠️ | greedy 한계 report 명시 |
| Q4 | "단순 uplift vs cost-aware 모델 차이?" | 동일 | `lift_analyze_campaign` → evaluation.json | 모델별 AUUC/Qini | ⚠️ | P1-B: compare_models tool |
| Q5 | "쿠폰이 손해인 고객군은 누구야?" | 동일 | `lift_analyze_campaign` → anti-targets.csv | anti-targets.csv | ❌ | P1-A: anti-target export |
| Q6 | "인과추론 결과를 믿어도 돼?" | 동일 | `lift_analyze_campaign` → trust.json | trust_level, warnings | ✅ | — |
| Q7 | "overlap 문제는 없어?" | 동일 + estimate_propensity | `lift_analyze_campaign(estimate_propensity=true)` | overlap_status, propensity_percentiles | ✅ | — |
| Q8 | "예산을 늘리면 얼마나 늘어나?" | 동일 | `lift_analyze_campaign` → budget-frontier.csv | cumulative_expected_gain by rank | ⚠️ | P1-C: budget_frontier tool |
| Q9 | "모델별 AUCC를 비교해줘." | 동일 | `lift_analyze_campaign` → evaluation.json, curves.csv | AUCC(수정 후), AUUC, Qini | ⚠️ | P0-B: AUCC 수정 + P1-B: compare tool |
| Q10 | "추천 대상자 CSV와 리포트를 만들어줘." | 동일 | `lift_analyze_campaign` → targets.csv + `lift_report` | targets.csv + report.md | ✅ | — |

---

## 5. 산출물

### 다음 작업 우선순위 Top 10

| 순위 | 작업 | 파일 |
|------|------|------|
| 1 | `npm view @mariozechner/pi-coding-agent` 접근성 수동 확인 | — |
| 2 | `lift doctor` Pi runtime 체크 추가 | `system/doctor.py` |
| 3 | AUCC 버그 수정 | `evaluation/metrics.py` |
| 4 | Anti-target export 구현 | `evaluation/metrics.py`, `workflow/run.py`, `workflow/report.py` |
| 5 | report.md do-not-treat 섹션 | `workflow/report.py` |
| 6 | Pi tool `lift_compare_models` | `pi_assets/lift_tools.mjs` |
| 7 | Pi tool `lift_budget_frontier` | `pi_assets/lift_tools.mjs` |
| 8 | `lift status` 대시보드 | `interfaces/cli.py` |
| 9 | `lift quickstart` 결과 안내 개선 | `interfaces/cli.py` |
| 10 | cost_aware / negative_uplift fixture 추가 | `fixtures/` |

### 사용자가 지금 바로 테스트 가능한 Happy Path (CLI only)

```bash
LIFT_PACKAGE=. sh scripts/install/install.sh
export PATH="$HOME/.local/bin:$PATH"
lift model login openai --method api-key --api-key "$OPENAI_API_KEY"
lift analyze fixtures/randomized_coupon.csv --seed 123
RUN=$(ls -t ~/.lift/outputs/ | head -1)
lift simulate "$RUN" --budget 100000000 --min-roi 1.5
lift report "$RUN"
```

### 테스트 전에 반드시 고쳐야 하는 Blockers

1. `npm view @mariozechner/pi-coding-agent` — Pi shell 전제 확인
2. AUCC 버그 (`metrics.py:47-48`) — Q9 결과 신뢰 불가
3. `lift doctor` Pi 미체크 — 설치 이상 진단 불가

### 다음 구현 시작 시 첫 번째 파일

**`src/lift/evaluation/metrics.py`** — AUCC 수정 + anti-target 로직 추가
