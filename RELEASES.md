# Release Notes

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
