#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m compileall -q src tests
"$PYTHON_BIN" -m unittest discover -s tests
"$PYTHON_BIN" -m build --no-isolation

echo "Build artifacts written to dist/"
