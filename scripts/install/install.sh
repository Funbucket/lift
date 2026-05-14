#!/usr/bin/env sh
set -eu

LIFT_HOME="${LIFT_HOME:-"$HOME/.lift"}"
LIFT_BIN_DIR="${LIFT_BIN_DIR:-"$HOME/.local/bin"}"
LIFT_SOURCE="${LIFT_SOURCE:-"$(pwd)"}"
VENV_DIR="$LIFT_HOME/venv"

if [ ! -f "$LIFT_SOURCE/pyproject.toml" ]; then
  echo "Lift source not found at $LIFT_SOURCE. Run this from the repo root or set LIFT_SOURCE." >&2
  exit 1
fi

mkdir -p "$LIFT_HOME" "$LIFT_BIN_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install "$LIFT_SOURCE"

ln -sf "$VENV_DIR/bin/lift" "$LIFT_BIN_DIR/lift"

echo "Lift installed."
echo "Launcher: $LIFT_BIN_DIR/lift"
echo "Home: $LIFT_HOME"
echo
echo "Make sure $LIFT_BIN_DIR is on PATH, then run:"
echo "  lift doctor"
