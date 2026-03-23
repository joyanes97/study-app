from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from study_app.automation import notebooklm_storage_path, run_automation
from study_app.markdown_loader import load_topics
from study_app.nanobot import system_prompt
from study_app.notebooklm import build_batch_script
from study_app.scheduler import build_daily_plan
from study_app.service import build_dashboard_data, progress_summary
from study_app.settings import load_settings
from study_app.state import load_progress


def resolve_root() -> Path:
    return Path("/home/jose/exam-study-app")


def resolve_date(raw: str) -> date:
    return date.today() if raw == "today" else date.fromisoformat(raw)


def build_context(root: Path):
    settings = load_settings(root)
    topics = load_topics(
        root / "data" / "content",
        settings.default_priority,
        settings.default_topic_weight,
    )
    progress = load_progress(root / "data" / "state", topics)
    return settings, topics, progress


def cmd_topics(root: Path) -> int:
    settings, topics, _ = build_context(root)
    print(f"Exam date: {settings.exam_date.isoformat()}")
    for topic in topics:
        print(
            f"- {topic.id} | {topic.subject} | {topic.title} | "
            f"priority={topic.priority} | weight={topic.estimated_weight}"
        )
    return 0


def cmd_plan(root: Path, plan_for: date) -> int:
    settings, topics, progress = build_context(root)
    plan = build_daily_plan(topics, progress, plan_for, settings)
    output = plan.to_markdown()
    state_dir = root / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    out_path = state_dir / "today-plan.md"
    out_path.write_text(output, encoding="utf-8")
    print(output, end="")
    print(f"Saved plan to {out_path}")
    return 0


def cmd_notebooklm_batch(root: Path) -> int:
    _, topics, _ = build_context(root)
    script = build_batch_script(root, topics)
    path = root / "data" / "state" / "notebooklm-batch.sh"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    print(f"Saved NotebookLM batch to {path}")
    return 0


def cmd_nanobot_config(root: Path) -> int:
    config_path = root / "config" / "nanobot.config.example.json"
    prompt_path = root / "data" / "state" / "nanobot-system-prompt.txt"
    prompt_path.write_text(system_prompt(root), encoding="utf-8")
    print(f"Nanobot config: {config_path}")
    print(f"System prompt: {prompt_path}")
    return 0


def cmd_automation(root: Path) -> int:
    report = run_automation(root)
    print(report["summary"])
    return 0


def cmd_progress(root: Path) -> int:
    data = progress_summary(root)
    daily = data["daily_session"]
    print(f"Session: {daily['status']}")
    print(
        f"Cards {len(daily['completed_cards'])}/{daily['target_cards']} | "
        f"Questions {len(daily['completed_questions'])}/{daily['target_questions']}"
    )
    print(data["automation_report"]["summary"])
    return 0


def cmd_notebooklm_auth(root: Path) -> int:
    storage = notebooklm_storage_path(root)
    print(f"NotebookLM storage: {storage}")
    print("ready" if storage.exists() else "missing")
    return 0


def cmd_serve(host: str, port: int) -> int:
    import uvicorn

    uvicorn.run("study_app.web:app", host=host, port=port, reload=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="study-app")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("topics")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--date", default="today", help="today or ISO date")

    subparsers.add_parser("notebooklm-batch")
    subparsers.add_parser("nanobot-config")
    subparsers.add_parser("automation-run")
    subparsers.add_parser("progress")
    subparsers.add_parser("notebooklm-auth")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()
    root = resolve_root()

    if args.command == "topics":
        return cmd_topics(root)
    if args.command == "plan":
        return cmd_plan(root, resolve_date(args.date))
    if args.command == "notebooklm-batch":
        return cmd_notebooklm_batch(root)
    if args.command == "nanobot-config":
        return cmd_nanobot_config(root)
    if args.command == "automation-run":
        return cmd_automation(root)
    if args.command == "progress":
        return cmd_progress(root)
    if args.command == "notebooklm-auth":
        return cmd_notebooklm_auth(root)
    if args.command == "serve":
        return cmd_serve(args.host, args.port)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
