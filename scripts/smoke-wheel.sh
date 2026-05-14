#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"
DIST_DIR="${DIST_DIR:-dist}"
SMOKE_DIR="${SMOKE_DIR:-}"

if [ -z "$SMOKE_DIR" ]; then
  SMOKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lift-wheel-smoke.XXXXXX")"
fi

WHEEL_PATH="$(find "$DIST_DIR" -maxdepth 1 -name 'lift_agent-*.whl' | sort | tail -n 1)"

if [ -z "$WHEEL_PATH" ]; then
  echo "No wheel found in $DIST_DIR. Run scripts/build.sh first." >&2
  exit 1
fi

VENV_DIR="$SMOKE_DIR/venv"
LIFT_HOME="$SMOKE_DIR/home"

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install "$WHEEL_PATH"

"$VENV_DIR/bin/lift" version
PATH="$VENV_DIR/bin:$PATH" LIFT_HOME="$LIFT_HOME" "$VENV_DIR/bin/lift" setup --overwrite
PATH="$VENV_DIR/bin:$PATH" LIFT_HOME="$LIFT_HOME" "$VENV_DIR/bin/lift" doctor
PATH="$VENV_DIR/bin:$PATH" LIFT_HOME="$LIFT_HOME" "$VENV_DIR/bin/lift" install-skills --target repo --project-root "$SMOKE_DIR" --overwrite
PATH="$VENV_DIR/bin:$PATH" LIFT_HOME="$LIFT_HOME" "$VENV_DIR/bin/lift" quickstart --budget 5 --min-roi 0.1

echo "Wheel smoke test passed: $WHEEL_PATH"
