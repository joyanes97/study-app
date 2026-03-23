#!/usr/bin/env bash
set -euo pipefail

. /home/jose/.config/exam-study-app/env
. /home/jose/exam-study-app/.venv/bin/activate
exec nanobot agent -c /home/jose/.nanobot-study/config.json "$@"
