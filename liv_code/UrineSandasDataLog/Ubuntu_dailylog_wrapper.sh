#!/usr/bin/env bash
set -e

SCRIPT_PATH="/home/dkvlko/OneDrive/DheerajOnHP/liv_code/UrineSandasDataLog/dailylog_server_u.py"
VENV_DIR="/home/dkvlko/python314_projects/venv_3.14"
VENV_PY="$VENV_DIR/bin/python"

if [[ ! -f "$SCRIPT_PATH" ]]; then
    echo "❌ Python script not found:"
    echo "   $SCRIPT_PATH"
    exit 1
fi

if [[ ! -x "$VENV_PY" ]]; then
    echo "❌ Virtual environment not found or invalid:"
    echo "   Expected: $VENV_PY"
    echo "   Create it with:"
    echo "   python3 -m venv $VENV_DIR"
    exit 1
fi

exec "$VENV_PY" "$SCRIPT_PATH" "$@"
