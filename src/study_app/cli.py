from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from study_app.automation import (
    mark_generation_notified,
    mark_generation_running,
    mark_reminder_sent,
    notebooklm_storage_path,
    run_automation,
    set_reminder_suppression,
)
from study_app.markdown_loader import load_topics
from study_app.nanobot import system_prompt
from study_app.notebooklm import build_batch_script
from study_app.pdf_ingest import ingest_pdf_inbox
from study_app.practical_cases import (
    build_practical_source_markdown,
    generate_practical_cases,
)
from study_app.scheduler import build_daily_plan
from study_app.service import build_dashboard_data, progress_summary
from study_app.settings import load_settings
from study_app.source_normalizer import ensure_normalized_source
from study_app.state import load_progress
from study_app.study_sqlite import get_study_db_path
from study_app.topic_splitter import split_block_markdown


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


def cmd_reminder_sent(root: Path, reminder_key: str) -> int:
    state = mark_reminder_sent(root, reminder_key)
    print(state["last_sent_key"])
    return 0


def cmd_suppress_reminders(root: Path, mode: str) -> int:
    state = set_reminder_suppression(root, mode == "on")
    print(f"suppress_reminders={state['suppress_reminders']}")
    return 0


def cmd_generation_notified(root: Path) -> int:
    state = mark_generation_notified(root)
    print(state["generation_complete_notified"])
    return 0


def cmd_generation_state(root: Path, mode: str, total: int, completed: int) -> int:
    state = mark_generation_running(
        root,
        running=(mode == "start"),
        total_topics=total,
        completed_topics=completed,
    )
    print(state["generation_running"])
    return 0


def cmd_ingest_pdf(root: Path) -> int:
    settings = load_settings(root)
    report = ingest_pdf_inbox(root, settings, root / "data" / "state")
    print(f"Ingested PDFs: {len(report['ingested'])}")
    print(f"Pending OCR: {len(report['pending_ocr'])}")
    return 0


def cmd_generate_practicals(root: Path, source_pdf: str) -> int:
    import subprocess

    source = Path(source_pdf)
    raw = subprocess.run(
        ["pdftotext", "-layout", "-nopgbrk", str(source), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    practical_dir = root / "data" / "content" / "practicals"
    practical_dir.mkdir(parents=True, exist_ok=True)
    source_md = practical_dir / "supuestos-practicos-base.md"
    source_md.write_text(
        "---\nsubject: practicos\ntopic: supuestos practicos\nsubtopic: base\npriority: high\nestimated_weight: 0.8\nstudy_enabled: false\n---\n\n"
        + build_practical_source_markdown(raw, "Supuestos prácticos"),
        encoding="utf-8",
    )
    generated_md = practical_dir / "supuestos-practicos-generados.md"
    generated = generate_practical_cases(
        source_md.read_text(encoding="utf-8"), generated_md
    )
    body = generated.read_text(encoding="utf-8")
    generated.write_text(
        "---\nsubject: practicos\ntopic: supuestos practicos\nsubtopic: generados\npriority: high\nestimated_weight: 1.0\n---\n\n"
        + body.lstrip(),
        encoding="utf-8",
    )
    print(f"Base practicals: {source_md}")
    print(f"Generated practicals: {generated_md}")
    return 0


def cmd_split_topics(root: Path) -> int:
    inbox_dir = root / "data" / "content" / "inbox"
    output_dir = root / "data" / "content" / "topics"
    written = []
    for path in sorted(inbox_dir.glob("*.md")):
        written.extend(split_block_markdown(path, output_dir))
    print(f"Split topic files: {len(written)}")
    return 0


def cmd_normalize_sources(root: Path) -> int:
    settings = load_settings(root)
    topics = load_topics(
        root / "data" / "content",
        settings.default_priority,
        settings.default_topic_weight,
    )
    written = [ensure_normalized_source(root, topic) for topic in topics]
    print(f"Normalized sources: {len(written)}")
    return 0


def cmd_sqlite_status(root: Path) -> int:
    db_path = get_study_db_path(root / "data" / "state")
    print(f"sqlite_db: {db_path}")
    print(f"exists: {db_path.exists()}")
    if db_path.exists():
        print(f"size_bytes: {db_path.stat().st_size}")
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
    reminder_parser = subparsers.add_parser("reminder-sent")
    reminder_parser.add_argument("--key", required=True)
    suppress_parser = subparsers.add_parser("suppress-reminders")
    suppress_parser.add_argument("--mode", choices=["on", "off"], required=True)
    subparsers.add_parser("generation-notified")
    generation_state_parser = subparsers.add_parser("generation-state")
    generation_state_parser.add_argument(
        "--mode", choices=["start", "finish"], required=True
    )
    generation_state_parser.add_argument("--total", type=int, default=0)
    generation_state_parser.add_argument("--completed", type=int, default=0)
    subparsers.add_parser("ingest-pdf")
    subparsers.add_parser("normalize-sources")
    subparsers.add_parser("split-topics")
    subparsers.add_parser("sqlite-status")
    practicals_parser = subparsers.add_parser("generate-practicals")
    practicals_parser.add_argument("--source-pdf", required=True)

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
    if args.command == "reminder-sent":
        return cmd_reminder_sent(root, args.key)
    if args.command == "suppress-reminders":
        return cmd_suppress_reminders(root, args.mode)
    if args.command == "generation-notified":
        return cmd_generation_notified(root)
    if args.command == "generation-state":
        return cmd_generation_state(root, args.mode, args.total, args.completed)
    if args.command == "ingest-pdf":
        return cmd_ingest_pdf(root)
    if args.command == "normalize-sources":
        return cmd_normalize_sources(root)
    if args.command == "sqlite-status":
        return cmd_sqlite_status(root)
    if args.command == "split-topics":
        return cmd_split_topics(root)
    if args.command == "generate-practicals":
        return cmd_generate_practicals(root, args.source_pdf)
    if args.command == "serve":
        return cmd_serve(args.host, args.port)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
