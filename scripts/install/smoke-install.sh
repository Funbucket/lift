#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"
DIST_DIR="${DIST_DIR:-dist}"
INSTALLER="${INSTALLER:-scripts/install/install.sh}"
SMOKE_DIR="${SMOKE_DIR:-}"

if [ -z "$SMOKE_DIR" ]; then
  SMOKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lift-install-smoke.XXXXXX")"
fi

WHEEL_PATH="$(find "$DIST_DIR" -maxdepth 1 -name 'lift_agent-*.whl' | sort | tail -n 1)"
if [ -z "$WHEEL_PATH" ]; then
  echo "No wheel found in $DIST_DIR. Run scripts/build.sh first." >&2
  exit 1
fi

case "$WHEEL_PATH" in
  /*) WHEEL_ABS="$WHEEL_PATH" ;;
  *) WHEEL_ABS="$(pwd)/$WHEEL_PATH" ;;
esac

LIFT_HOME="$SMOKE_DIR/home" \
LIFT_BIN_DIR="$SMOKE_DIR/bin" \
LIFT_PACKAGE_URL="file://$WHEEL_ABS" \
PYTHON_BIN="$PYTHON_BIN" \
  sh "$INSTALLER"

PATH="$SMOKE_DIR/bin:$PATH" LIFT_HOME="$SMOKE_DIR/home" lift setup --overwrite
BRIDGE_PATH="$(PATH="$SMOKE_DIR/bin:$PATH" LIFT_HOME="$SMOKE_DIR/home" lift model bridge-path --raw)"
test -f "$BRIDGE_PATH"
PATH="$SMOKE_DIR/bin:$PATH" LIFT_HOME="$SMOKE_DIR/home" lift doctor
PATH="$SMOKE_DIR/bin:$PATH" LIFT_HOME="$SMOKE_DIR/home" lift install-skills --target repo --project-root "$SMOKE_DIR" --overwrite
PATH="$SMOKE_DIR/bin:$PATH" LIFT_HOME="$SMOKE_DIR/home" lift quickstart --budget 5 --min-roi 0.1

echo "Installer smoke test passed: $WHEEL_ABS"
