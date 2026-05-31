# Release Notes

## 0.1.8

- Fix AUCC metric: was incorrectly identical to AUUC; now uses incremental cost as the x-axis (gain-vs-cost curve).
- Export anti-targets (do-not-target segment): `anti-targets.csv` written by `lift analyze` and `lift simulate`. Customers with non-positive predicted uplift score or gain.
- Add `lift doctor` Pi runtime checks: node availability, pi_cli, pi extension, and OAuth bridge now reported in `checks` and `pi_runtime` fields.
- Add `lift compare-models <run-id>` command: returns per-model AUUC, AUCC, Qini, and gain-at-budget/ROI leaderboard as JSON.
- Add `lift budget-frontier <run-id>` command: returns the budget-gain frontier curve rows as JSON.
- Add `lift_compare_models` and `lift_budget_frontier` Pi shell tools backed by the new commands.
- Improve `lift quickstart` output: includes `report_path` and `next_steps` hints.

## 0.1.4

- Replace hand-rolled setup selection with a Feynman-style `@clack/prompts` Node setup helper.
- Bundle `setup_prompt.mjs` with the package and install it beside the OAuth bridge.
- Use `@clack/prompts` for OAuth bridge text prompts.

## 0.1.3

- Make `lift setup` start with a Feynman-style OAuth/API-key model access choice in interactive terminals.
- Install the Pi-compatible OAuth bridge automatically when `node` and `npm` are available.
- Let OAuth bridge progress and browser-login instructions stream directly to the terminal.

## 0.1.2

- Accept slash and bare commands in the local REPL, including `/help` and `help`.

## 0.1.1

- Add Feynman-style terminal dashboard for `lift`.
- Add `lift model` and `lift agent` command groups.
- Add optional Pi-compatible OAuth bridge packaging and installer support.
- Include the OAuth bridge asset in wheel/sdist builds.

## 0.1.0

- Local-first Lift CLI with install scripts.
- Baseline and Duality R-learner workflow.
- scikit-learn based preprocessing and configurable estimators.
- Trust diagnostics, ranking evaluation, budget simulation, target export, report generation.
- REPL, setup, skills installer, quickstart, and packaged example workflow.
