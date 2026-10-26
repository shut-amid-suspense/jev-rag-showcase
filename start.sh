#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "First prepare the project environment:"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi
export GRADIO_ANALYTICS_ENABLED=False
export GRADIO_SERVER_NAME=127.0.0.1
exec .venv/bin/python app.py
