from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from study_app.markdown_loader import load_topics
from study_app.pdf_ingest import ingest_pdf_inbox
from study_app.json_store import write_json
from study_app.settings import load_settings
from study_app.state import load_progress, save_progress
from study_app.study_store import (
    ensure_daily_session,
    load_automation_report,
    load_generation_jobs,
    load_notebook_map,
    load_source_index,
    save_automation_report,
    save_generation_jobs,
    save_notebook_map,
    save_source_index,
    sync_generated_artifacts,
    topic_source_hash,
)


def notebooklm_storage_path(root: Path) -> Path:
    return root / "notebooklm-home" / "storage_state.json"


def notebooklm_is_ready(root: Path) -> bool:
    return notebooklm_storage_path(root).exists()


async def _generate_with_notebooklm(
    root: Path, changed_topics: list, state_dir: Path
) -> tuple[list[str], list[str]]:
    from notebooklm import NotebookLMClient  # type: ignore[import-not-found]
    from notebooklm.types import QuizDifficulty, QuizQuantity  # type: ignore[import-not-found]

    generated_topics: list[str] = []
    pending_auth_topics: list[str] = []
    notebook_map = load_notebook_map(state_dir)
    storage_path = notebooklm_storage_path(root)
    if not storage_path.exists():
        return generated_topics, [topic.id for topic in changed_topics]

    async with await NotebookLMClient.from_storage(str(storage_path)) as client:
        for topic in changed_topics:
            try:
                previous = notebook_map.get(topic.id)
                if previous:
                    try:
                        await client.notebooks.delete(previous)
                    except Exception:
                        pass
                notebook = await client.notebooks.create(
                    f"{topic.subject} - {topic.title} [{topic.id}]"
                )
                notebook_map[topic.id] = notebook.id
                await client.sources.add_file(
                    notebook.id, str(topic.source_path), wait=True
                )
                flashcards = await client.artifacts.generate_flashcards(
                    notebook.id,
                    difficulty=QuizDifficulty.MEDIUM,
                    quantity=QuizQuantity.MORE,
                )
                await client.artifacts.wait_for_completion(
                    notebook.id, flashcards.task_id
                )
                await client.artifacts.download_flashcards(
                    notebook.id,
                    str(root / "data" / "generated" / f"{topic.id}-cards.json"),
                    output_format="json",
                )
                quiz = await client.artifacts.generate_quiz(
                    notebook.id,
                    difficulty=QuizDifficulty.HARD,
                    quantity=QuizQuantity.STANDARD,
                )
                await client.artifacts.wait_for_completion(notebook.id, quiz.task_id)
                await client.artifacts.download_quiz(
                    notebook.id,
                    str(root / "data" / "generated" / f"{topic.id}-quiz.json"),
                    output_format="json",
                )
                generated_topics.append(topic.id)
            except Exception:
                pending_auth_topics.append(topic.id)

    save_notebook_map(state_dir, notebook_map)
    return generated_topics, pending_auth_topics


def run_automation(root: Path) -> dict:
    settings = load_settings(root)
    state_dir = root / "data" / "state"
    pdf_report = ingest_pdf_inbox(root, settings, state_dir)
    topics = load_topics(
        root / "data" / "content",
        settings.default_priority,
        settings.default_topic_weight,
    )
    generated_dir = root / "data" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    progress = load_progress(state_dir, topics)
    source_index = load_source_index(state_dir)
    generation_jobs = load_generation_jobs(state_dir)

    new_index = {}
    changed_topics = []
    for topic in topics:
        entry = {
            "hash": topic_source_hash(topic),
            "updated_at": datetime.now().isoformat(),
            "path": str(topic.source_path),
            "title": topic.title,
        }
        new_index[topic.id] = entry
        previous = source_index.get(topic.id)
        if not previous or previous.get("hash") != entry["hash"]:
            changed_topics.append(topic)

    generated_topics: list[str] = []
    pending_auth_topics: list[str] = []
    pending_ocr_topics = [item["source_pdf"] for item in pdf_report["pending_ocr"]]
    if changed_topics:
        for topic in changed_topics:
            generation_jobs.append(
                {
                    "topic_id": topic.id,
                    "title": topic.title,
                    "status": "queued",
                    "created_at": datetime.now().isoformat(),
                }
            )
        if notebooklm_is_ready(root):
            generated_topics, pending_auth_topics = asyncio.run(
                _generate_with_notebooklm(root, changed_topics, state_dir)
            )
        else:
            pending_auth_topics = [topic.id for topic in changed_topics]

    cards, questions = sync_generated_artifacts(state_dir, generated_dir, topics)
    cards_by_topic: dict[str, int] = {}
    questions_by_topic: dict[str, int] = {}
    for card in cards:
        cards_by_topic[card["topic_id"]] = cards_by_topic.get(card["topic_id"], 0) + 1
    for question in questions:
        questions_by_topic[question["topic_id"]] = (
            questions_by_topic.get(question["topic_id"], 0) + 1
        )

    for topic in topics:
        topic_progress = progress[topic.id]
        topic_progress.generated_cards = cards_by_topic.get(topic.id, 0)
        topic_progress.generated_quiz_items = questions_by_topic.get(topic.id, 0)
    save_progress(state_dir, progress)

    for job in generation_jobs:
        if job["topic_id"] in generated_topics:
            job["status"] = "generated"
            job["completed_at"] = datetime.now().isoformat()
        elif job["topic_id"] in pending_auth_topics:
            job["status"] = "pending_notebooklm_auth"

    report = load_automation_report(state_dir)
    today_session = ensure_daily_session(
        state_dir, datetime.now().date(), cards[:12], questions[:10]
    )
    completed_cards = len(today_session.get("completed_cards", []))
    completed_questions = len(today_session.get("completed_questions", []))
    target_cards = today_session.get("target_cards", 0)
    target_questions = today_session.get("target_questions", 0)
    progress_ratio = 1.0
    total_target = target_cards + target_questions
    total_done = completed_cards + completed_questions
    if total_target > 0:
        progress_ratio = total_done / total_target

    now = datetime.now()
    needs_reminder = (
        today_session.get("status") != "completed"
        and now.hour in settings.reminder_hours
    )
    summary_parts = []
    if changed_topics:
        summary_parts.append(
            f"Temas nuevos o modificados: {', '.join(topic.title for topic in changed_topics)}"
        )
    if pdf_report["ingested"]:
        summary_parts.append(
            f"PDFs convertidos a Markdown: {len(pdf_report['ingested'])}"
        )
    if generated_topics:
        summary_parts.append(f"Material generado para {len(generated_topics)} temas")
    if pending_auth_topics:
        summary_parts.append(
            "NotebookLM necesita autenticación para generar material nuevo"
        )
    if pending_ocr_topics:
        summary_parts.append(
            f"OCR pendiente o fallido en {len(pending_ocr_topics)} PDFs"
        )
    if needs_reminder:
        summary_parts.append(
            f"Estudio diario incompleto: {total_done}/{total_target} actividades completadas"
        )
    if not summary_parts:
        summary_parts.append("Sin cambios nuevos. La automatización está al día.")

    report.update(
        {
            "generated_topics": generated_topics,
            "pending_auth_topics": pending_auth_topics,
            "pending_ocr_topics": pending_ocr_topics,
            "new_material_topics": [topic.id for topic in changed_topics],
            "ingested_pdfs": pdf_report["ingested"],
            "daily_session": {
                "date": today_session["date"],
                "status": today_session["status"],
                "completed_cards": completed_cards,
                "target_cards": target_cards,
                "completed_questions": completed_questions,
                "target_questions": target_questions,
                "progress_ratio": round(progress_ratio, 2),
            },
            "needs_reminder": needs_reminder,
            "last_run": now.isoformat(),
            "summary": " | ".join(summary_parts),
        }
    )
    save_source_index(state_dir, new_index)
    save_generation_jobs(state_dir, generation_jobs)
    save_automation_report(state_dir, report)
    write_json(state_dir / "automation_status.json", report)
    return report
