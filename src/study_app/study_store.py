from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

from study_app.json_store import read_json, write_json
from study_app.models import Topic


def _path(state_dir: Path, name: str) -> Path:
    return state_dir / name


def load_cards(state_dir: Path) -> list[dict]:
    return read_json(_path(state_dir, "cards.json"), [])


def save_cards(state_dir: Path, cards: list[dict]) -> Path:
    return write_json(_path(state_dir, "cards.json"), cards)


def load_questions(state_dir: Path) -> list[dict]:
    return read_json(_path(state_dir, "questions.json"), [])


def save_questions(state_dir: Path, questions: list[dict]) -> Path:
    return write_json(_path(state_dir, "questions.json"), questions)


def load_card_reviews(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "card_reviews.json"), {})


def save_card_reviews(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "card_reviews.json"), payload)


def load_question_attempts(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "question_attempts.json"), {})


def save_question_attempts(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "question_attempts.json"), payload)


def load_source_index(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "source_index.json"), {})


def save_source_index(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "source_index.json"), payload)


def load_generation_jobs(state_dir: Path) -> list[dict]:
    return read_json(_path(state_dir, "generation_jobs.json"), [])


def save_generation_jobs(state_dir: Path, jobs: list[dict]) -> Path:
    return write_json(_path(state_dir, "generation_jobs.json"), jobs)


def load_notebook_map(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "notebooklm_map.json"), {})


def save_notebook_map(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "notebooklm_map.json"), payload)


def load_daily_sessions(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "daily_sessions.json"), {})


def save_daily_sessions(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "daily_sessions.json"), payload)


def load_automation_report(state_dir: Path) -> dict:
    return read_json(
        _path(state_dir, "automation_report.json"),
        {
            "generated_topics": [],
            "pending_auth_topics": [],
            "new_material_topics": [],
            "daily_session": {},
            "needs_reminder": False,
            "last_run": None,
            "summary": "",
        },
    )


def save_automation_report(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "automation_report.json"), payload)


def topic_source_hash(topic: Topic) -> str:
    raw = topic.body.encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def sync_generated_artifacts(
    state_dir: Path, generated_dir: Path, topics: list[Topic]
) -> tuple[list[dict], list[dict]]:
    cards_by_id: dict[str, dict] = {}
    questions_by_id: dict[str, dict] = {}
    topic_ids = {topic.id for topic in topics}

    for path in sorted(generated_dir.glob("*-cards.json")):
        topic_id = path.name[: -len("-cards.json")]
        if topic_id not in topic_ids:
            continue
        payload = read_json(path, {"cards": []})
        for index, card in enumerate(payload.get("cards", []), start=1):
            card_id = f"{topic_id}-card-{index}"
            cards_by_id[card_id] = {
                "id": card_id,
                "topic_id": topic_id,
                "title": payload.get("title") or "Flashcards",
                "front": card.get("front") or card.get("f") or "",
                "back": card.get("back") or card.get("b") or "",
                "source_file": path.name,
            }

    for path in sorted(generated_dir.glob("*-quiz.json")):
        topic_id = path.name[: -len("-quiz.json")]
        if topic_id not in topic_ids:
            continue
        payload = read_json(path, {"questions": []})
        for index, question in enumerate(payload.get("questions", []), start=1):
            question_id = f"{topic_id}-question-{index}"
            options = []
            for opt_index, option in enumerate(
                question.get("answerOptions", []), start=1
            ):
                options.append(
                    {
                        "id": f"{question_id}-option-{opt_index}",
                        "text": option.get("text", ""),
                        "is_correct": bool(option.get("isCorrect", False)),
                    }
                )
            questions_by_id[question_id] = {
                "id": question_id,
                "topic_id": topic_id,
                "title": payload.get("title") or "Quiz",
                "question": question.get("question", ""),
                "hint": question.get("hint", ""),
                "options": options,
                "source_file": path.name,
            }

    cards = list(cards_by_id.values())
    questions = list(questions_by_id.values())
    save_cards(state_dir, cards)
    save_questions(state_dir, questions)
    return cards, questions


def ensure_daily_session(
    state_dir: Path, session_date: date, cards: list[dict], questions: list[dict]
) -> dict:
    sessions = load_daily_sessions(state_dir)
    key = session_date.isoformat()
    existing = sessions.get(key)
    if existing:
        existing.setdefault("completed_cards", [])
        existing.setdefault("completed_questions", [])
        existing.setdefault("status", "pending")
        existing["target_cards"] = max(existing.get("target_cards", 0), len(cards))
        existing["target_questions"] = max(
            existing.get("target_questions", 0), len(questions)
        )
        sessions[key] = existing
        save_daily_sessions(state_dir, sessions)
        return existing

    session = {
        "date": key,
        "target_cards": len(cards),
        "target_questions": len(questions),
        "completed_cards": [],
        "completed_questions": [],
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
    }
    sessions[key] = session
    save_daily_sessions(state_dir, sessions)
    return session


def update_daily_session_completion(
    state_dir: Path, session_date: date, item_type: str, item_id: str
) -> dict:
    sessions = load_daily_sessions(state_dir)
    key = session_date.isoformat()
    session = sessions.setdefault(
        key,
        {
            "date": key,
            "target_cards": 0,
            "target_questions": 0,
            "completed_cards": [],
            "completed_questions": [],
            "status": "pending",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
        },
    )
    target_key = "completed_cards" if item_type == "card" else "completed_questions"
    if item_id not in session[target_key]:
        session[target_key].append(item_id)

    cards_done = len(session["completed_cards"]) >= session.get("target_cards", 0)
    questions_done = len(session["completed_questions"]) >= session.get(
        "target_questions", 0
    )
    if session.get("target_cards", 0) == 0:
        cards_done = True
    if session.get("target_questions", 0) == 0:
        questions_done = True
    if cards_done and questions_done:
        session["status"] = "completed"
        session["completed_at"] = datetime.now().isoformat()
    else:
        session["status"] = "in_progress"

    sessions[key] = session
    save_daily_sessions(state_dir, sessions)
    return session


def record_card_review(state_dir: Path, card_id: str, rating: str) -> dict:
    reviews = load_card_reviews(state_dir)
    review = reviews.get(card_id, {"review_count": 0})
    today = date.today()
    intervals = {
        "again": 0,
        "hard": 1,
        "good": 3,
        "easy": 7,
    }
    review["last_rating"] = rating
    review["last_reviewed_at"] = datetime.now().isoformat()
    review["review_count"] = int(review.get("review_count", 0)) + 1
    review["next_due"] = (today + timedelta(days=intervals.get(rating, 1))).isoformat()
    reviews[card_id] = review
    save_card_reviews(state_dir, reviews)
    return review


def record_question_attempt(
    state_dir: Path, question_id: str, selected_option: str, is_correct: bool
) -> dict:
    attempts = load_question_attempts(state_dir)
    item = attempts.get(question_id, {"attempt_count": 0, "correct_count": 0})
    item["last_attempted_at"] = datetime.now().isoformat()
    item["last_selected_option"] = selected_option
    item["attempt_count"] = int(item.get("attempt_count", 0)) + 1
    item["correct_count"] = int(item.get("correct_count", 0)) + (1 if is_correct else 0)
    item["last_correct"] = is_correct
    attempts[question_id] = item
    save_question_attempts(state_dir, attempts)
    return item
