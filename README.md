# Exam Study App

Study planner for topic-based Markdown notes with one global exam date.

## What is running now

- Planner backend and UI under `/home/jose/exam-study-app`
- Web UI reachable at `http://192.168.3.29:8765`
- Nanobot config stored in `/home/jose/.nanobot-study/config.json`
- Nanobot user service stored in `/home/jose/.config/systemd/user/nanobot-study-gateway.service`

## Main folders

- `config/exam_config.json`: exam date and planning settings
- `data/content/`: your Markdown notes by topic
- `data/generated/`: generated NotebookLM JSON outputs
- `data/state/`: plan of the day and helper files
- `src/study_app/`: planner and web app code
- `scripts/`: helper launchers

## Quick start

```bash
cd /home/jose/exam-study-app
. .venv/bin/activate

study-app topics
study-app plan --date today
study-app notebooklm-batch
study-app serve --host 0.0.0.0 --port 8765
```

## Daily workflow

1. Copy your Markdown topic files into `data/content/`.
2. Update `config/exam_config.json` with the real exam date.
3. Run `/home/jose/exam-study-app/scripts/run_daily_cycle.sh`.
4. Open the UI in the browser.
5. Use `/home/jose/exam-study-app/data/state/notebooklm-batch.sh` to generate flashcards and quizzes in NotebookLM.
6. Use `/home/jose/exam-study-app/scripts/run_nanobot.sh` to start Nanobot with GLM.

## UI sections

- `/`: dashboard with today's study plan
- `/topics`: all topics ordered by urgency
- `/topics/<id>`: readable view of one topic
- `/api/plan`: JSON daily plan
- `/api/topics`: JSON topic list

## Notes

- Markdown files are the source of truth.
- The scheduler adapts work by days left until the exam.
- NotebookLM is the generation layer for flashcards and quizzes.
- Nanobot is the orchestration layer using GLM.

## Services

The server now runs these systemd units:

- `exam-study-web.service`: serves the web UI on port `8765`
- `exam-study-daily.timer`: runs the planner every day at `05:30`
- `exam-study-daily.service`: oneshot job triggered by the timer
- `nanobot-study-gateway.service`: Nanobot gateway as a hardened user service for `jose`

Useful commands:

```bash
sudo systemctl status exam-study-web.service
sudo systemctl restart exam-study-web.service
sudo systemctl status exam-study-daily.timer
sudo systemctl start exam-study-daily.service
sudo -u jose systemctl --user status nanobot-study-gateway.service
sudo -u jose systemctl --user restart nanobot-study-gateway.service
sudo -u jose journalctl --user -u nanobot-study-gateway.service -n 100 --no-pager
```

Service templates tracked in this repo:

- `deploy/systemd/exam-study-web.service`
- `deploy/systemd/exam-study-daily.service`
- `deploy/systemd/exam-study-daily.timer`
- `deploy/systemd/nanobot-study-gateway.service`
