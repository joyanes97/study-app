#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jose/exam-study-app"
set -a
. /home/jose/.config/exam-study-app/env
set +a
. "$ROOT/.venv/bin/activate"

exec study-app automation-run
