#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "Creating .venv ..."
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import PySide6, kociemba" >/dev/null 2>&1; then
    echo "Installing dependencies ..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python main.py "$@"
