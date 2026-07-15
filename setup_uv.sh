#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  python -m pip install -q -U uv
fi

uv sync

uv run python -m ipykernel install \
  --user \
  --name managed-agents-labs \
  --display-name "Managed Agents Labs (.venv)"

echo "Created .venv and installed shared lab dependencies."
echo "Registered Jupyter kernel: Managed Agents Labs (.venv)"
echo "Run scripts without activation, for example:"
echo "  cd lab_02_first_python_session"
echo "  uv run --project .. --env-file ../.env python lab02.py"
