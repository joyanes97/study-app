#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jose/exam-study-app"
. "$ROOT/.venv/bin/activate"

exec study-app automation-run
