#!/usr/bin/env sh
set -eu

LIFT_HOME="${LIFT_HOME:-"$HOME/.lift"}"
LIFT_BIN_DIR="${LIFT_BIN_DIR:-"$HOME/.local/bin"}"
LIFT_VERSION="${LIFT_VERSION:-0.1.3}"
LIFT_PACKAGE="${LIFT_PACKAGE:-${LIFT_SOURCE:-}}"
LIFT_PACKAGE_URL="${LIFT_PACKAGE_URL:-}"
LIFT_DEFAULT_RELEASE_BASE_URL="https://github.com/Funbucket/lift/releases/latest/download"
LIFT_RELEASE_BASE_URL="${LIFT_RELEASE_BASE_URL:-}"
LIFT_INSTALL_OAUTH_BRIDGE="${LIFT_INSTALL_OAUTH_BRIDGE:-auto}"
VENV_DIR="$LIFT_HOME/venv"

if [ -z "$LIFT_PACKAGE" ]; then
  if [ -n "$LIFT_PACKAGE_URL" ]; then
    LIFT_INSTALL_TMP="$(mktemp -d "${TMPDIR:-/tmp}/lift-install.XXXXXX")"
    LIFT_PACKAGE="$LIFT_INSTALL_TMP/lift_agent-$LIFT_VERSION-py3-none-any.whl"
    curl -fsSL "$LIFT_PACKAGE_URL" -o "$LIFT_PACKAGE"
  elif [ -n "$LIFT_RELEASE_BASE_URL" ]; then
    LIFT_INSTALL_TMP="$(mktemp -d "${TMPDIR:-/tmp}/lift-install.XXXXXX")"
    LIFT_PACKAGE="$LIFT_INSTALL_TMP/lift_agent-$LIFT_VERSION-py3-none-any.whl"
    curl -fsSL "$LIFT_RELEASE_BASE_URL/lift_agent-$LIFT_VERSION-py3-none-any.whl" -o "$LIFT_PACKAGE"
  elif [ -n "$LIFT_DEFAULT_RELEASE_BASE_URL" ]; then
    LIFT_INSTALL_TMP="$(mktemp -d "${TMPDIR:-/tmp}/lift-install.XXXXXX")"
    LIFT_PACKAGE="$LIFT_INSTALL_TMP/lift_agent-$LIFT_VERSION-py3-none-any.whl"
    curl -fsSL "$LIFT_DEFAULT_RELEASE_BASE_URL/lift_agent-$LIFT_VERSION-py3-none-any.whl" -o "$LIFT_PACKAGE"
  elif [ -f "$(pwd)/pyproject.toml" ]; then
    LIFT_PACKAGE="$(pwd)"
  else
    echo "Lift package not specified." >&2
    echo "Set LIFT_PACKAGE, LIFT_PACKAGE_URL, or LIFT_RELEASE_BASE_URL." >&2
    exit 1
  fi
fi

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

if [ "$LIFT_INSTALL_OAUTH_BRIDGE" = "auto" ]; then
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    LIFT_INSTALL_OAUTH_BRIDGE="1"
  else
    LIFT_INSTALL_OAUTH_BRIDGE="0"
  fi
fi

if [ "$LIFT_INSTALL_OAUTH_BRIDGE" = "1" ]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "LIFT_INSTALL_OAUTH_BRIDGE=1 requires node on PATH." >&2
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "LIFT_INSTALL_OAUTH_BRIDGE=1 requires npm on PATH." >&2
    exit 1
  fi
  BRIDGE_DIR="$LIFT_HOME/oauth-bridge"
  BRIDGE_SOURCE="$("$VENV_DIR/bin/lift" model bridge-path --raw)"
  mkdir -p "$BRIDGE_DIR"
  cp "$BRIDGE_SOURCE" "$BRIDGE_DIR/pi_auth_bridge.mjs"
  (cd "$BRIDGE_DIR" && npm install --omit=dev @mariozechner/pi-coding-agent@^0.73.0)
fi

echo "Lift installed."
echo "Launcher: $LIFT_BIN_DIR/lift"
echo "Home: $LIFT_HOME"
echo "Package: $LIFT_PACKAGE"
echo "Version: $LIFT_VERSION"
if [ "$LIFT_INSTALL_OAUTH_BRIDGE" = "1" ]; then
  echo "OAuth bridge: $LIFT_HOME/oauth-bridge/pi_auth_bridge.mjs"
fi
echo
echo "Make sure $LIFT_BIN_DIR is on PATH, then run:"
echo "  lift setup"
echo "  lift doctor"
echo "  lift quickstart"
