#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jose/exam-study-app"
. "$ROOT/.venv/bin/activate"
exec study-app serve --host 0.0.0.0 --port 8765
