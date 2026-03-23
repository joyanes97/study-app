#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jose/exam-study-app"
. "$ROOT/.venv/bin/activate"

study-app plan --date today
study-app notebooklm-batch
study-app nanobot-config
study-app automation-run

echo "Daily cycle prepared in $ROOT/data/state"
