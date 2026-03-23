#!/usr/bin/env bash
set -euo pipefail

set -a
. /home/jose/.config/exam-study-app/env
set +a
. /home/jose/exam-study-app/.venv/bin/activate
exec nanobot agent -c /home/jose/.nanobot-study/config.json "$@"
