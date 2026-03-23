#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jose/exam-study-app"
cd "$ROOT"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e .
echo "Bootstrap complete. Activate with: . $ROOT/.venv/bin/activate"
