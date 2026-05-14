#!/usr/bin/env sh
set -eu

LIFT_HOME="${LIFT_HOME:-"$HOME/.lift"}"
LIFT_BIN_DIR="${LIFT_BIN_DIR:-"$HOME/.local/bin"}"
LIFT_PACKAGE="${LIFT_PACKAGE:-${LIFT_SOURCE:-"$(pwd)"}}"
VENV_DIR="$LIFT_HOME/venv"

if [ -d "$LIFT_PACKAGE" ] && [ ! -f "$LIFT_PACKAGE/pyproject.toml" ]; then
  echo "Lift source not found at $LIFT_PACKAGE. Run this from the repo root or set LIFT_PACKAGE." >&2
  exit 1
fi

if [ ! -d "$LIFT_PACKAGE" ] && [ ! -f "$LIFT_PACKAGE" ]; then
  echo "Lift package not found at $LIFT_PACKAGE. Set LIFT_PACKAGE to a source directory, wheel, or sdist." >&2
  exit 1
fi

mkdir -p "$LIFT_HOME" "$LIFT_BIN_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install "$LIFT_PACKAGE"

ln -sf "$VENV_DIR/bin/lift" "$LIFT_BIN_DIR/lift"

echo "Lift installed."
echo "Launcher: $LIFT_BIN_DIR/lift"
echo "Home: $LIFT_HOME"
echo "Package: $LIFT_PACKAGE"
echo
echo "Make sure $LIFT_BIN_DIR is on PATH, then run:"
echo "  lift doctor"
echo "  lift quickstart"
