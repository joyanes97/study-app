from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

from study_app.json_store import read_json, write_json
from study_app.models import Topic
from study_app.targets import estimate_target_cards, estimate_target_questions


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


def load_attempt_events(state_dir: Path) -> list[dict]:
    return read_json(_path(state_dir, "attempt_events.json"), [])


def save_attempt_events(state_dir: Path, payload: list[dict]) -> Path:
    return write_json(_path(state_dir, "attempt_events.json"), payload)


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
            "pending_ocr_topics": [],
            "new_material_topics": [],
            "ingested_pdfs": [],
            "daily_session": {},
            "needs_reminder": False,
            "last_run": None,
            "summary": "",
        },
    )


def save_automation_report(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "automation_report.json"), payload)


def load_pdf_ingest_index(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "pdf_ingest_index.json"), {})


def save_pdf_ingest_index(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "pdf_ingest_index.json"), payload)


def load_reminder_state(state_dir: Path) -> dict:
    return read_json(_path(state_dir, "reminder_state.json"), {})


def save_reminder_state(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "reminder_state.json"), payload)


def load_notification_state(state_dir: Path) -> dict:
    return read_json(
        _path(state_dir, "notification_state.json"),
        {
            "suppress_reminders": False,
            "generation_complete_notified": False,
            "generation_running": False,
        },
    )


def save_notification_state(state_dir: Path, payload: dict) -> Path:
    return write_json(_path(state_dir, "notification_state.json"), payload)


def topic_source_hash(topic: Topic) -> str:
    raw = topic.body.encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def sync_generated_artifacts(
    state_dir: Path, generated_dir: Path, topics: list[Topic]
) -> tuple[list[dict], list[dict]]:
    cards_by_id: dict[str, dict] = {}
    questions_by_id: dict[str, dict] = {}
    topic_ids = {topic.id for topic in topics}

    topic_map = {topic.id: topic for topic in topics}

    for path in sorted(generated_dir.glob("*-cards.json")):
        topic_id = path.name[: -len("-cards.json")]
        if topic_id not in topic_ids:
            continue
        payload = read_json(path, {"cards": []})
        topic = topic_map[topic_id]
        limit = estimate_target_cards(topic.title, topic.body)
        for index, card in enumerate(payload.get("cards", [])[:limit], start=1):
            card_id = f"{topic_id}-card-{index}"
            cards_by_id[card_id] = {
                "id": card_id,
                "topic_id": topic_id,
                "content_type": topic.content_type,
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
        topic = topic_map[topic_id]
        limit = estimate_target_questions(topic.title, topic.body)
        for index, question in enumerate(payload.get("questions", [])[:limit], start=1):
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
                "content_type": topic.content_type,
                "title": payload.get("title") or "Quiz",
                "question": question.get("question", ""),
                "hint": question.get("hint", ""),
                "explanation": question.get("explanation")
                or question.get("hint")
                or "",
                "options": options,
                "option_explanations": _option_explanations(
                    options,
                    question.get("hint") or question.get("explanation") or "",
                ),
                "source_file": path.name,
            }

    cards = list(cards_by_id.values())
    questions = list(questions_by_id.values())
    save_cards(state_dir, cards)
    save_questions(state_dir, questions)
    return cards, questions


def _option_explanations(options: list[dict], explanation: str) -> dict[str, str]:
    correct_text = "La opcion correcta coincide con el contenido del tema."
    wrong_text = (
        explanation.strip()
        or "Este distractor no se ajusta al punto principal que aparece en el temario."
    )
    return {
        option["id"]: (correct_text if option["is_correct"] else wrong_text)
        for option in options
    }


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
    return _record_card_review_legacy(state_dir, card_id, rating)


def _record_card_review_legacy(state_dir: Path, card_id: str, rating: str) -> dict:
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
    return _record_question_attempt_legacy(
        state_dir, question_id, selected_option, is_correct
    )


def _record_question_attempt_legacy(
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


def record_card_review_event(
    state_dir: Path,
    card_id: str,
    rating: str,
    confidence: str,
    shown_at: str | None,
    topic_id: str | None = None,
) -> dict:
    reviews = load_card_reviews(state_dir)
    events = load_attempt_events(state_dir)
    review = reviews.get(
        card_id, {"review_count": 0, "difficulty": 0.5, "stability": 1.0}
    )
    now = datetime.now()
    response_time_ms = _response_ms(shown_at, now)
    confidence_factor = {"low": 0.85, "medium": 1.0, "high": 1.15}.get(confidence, 1.0)
    interval_days = {
        "again": 0,
        "hard": 1,
        "good": 3,
        "easy": 6,
    }.get(rating, 1)
    interval_days = max(0, int(round(interval_days * confidence_factor)))

    review["last_rating"] = rating
    review["last_confidence"] = confidence
    review["last_reviewed_at"] = now.isoformat()
    review["last_response_ms"] = response_time_ms
    review["review_count"] = int(review.get("review_count", 0)) + 1
    review["success_count"] = int(review.get("success_count", 0)) + (
        0 if rating == "again" else 1
    )
    review["lapse_count"] = int(review.get("lapse_count", 0)) + (
        1 if rating == "again" else 0
    )
    review["difficulty"] = _bounded(
        float(review.get("difficulty", 0.5))
        + {"again": 0.18, "hard": 0.08, "good": -0.04, "easy": -0.08}.get(rating, 0),
        0.1,
        1.0,
    )
    review["stability"] = _bounded(
        float(review.get("stability", 1.0))
        + {"again": -0.3, "hard": 0.15, "good": 0.5, "easy": 0.8}.get(rating, 0.2),
        0.2,
        30.0,
    )
    review["next_due"] = (date.today() + timedelta(days=interval_days)).isoformat()
    reviews[card_id] = review
    save_card_reviews(state_dir, reviews)

    events.append(
        {
            "item_id": card_id,
            "item_type": "card",
            "topic_id": topic_id,
            "rating": rating,
            "confidence": confidence,
            "response_time_ms": response_time_ms,
            "is_correct": rating != "again",
            "answered_at": now.isoformat(),
        }
    )
    save_attempt_events(state_dir, events)
    return review


def record_question_attempt_event(
    state_dir: Path,
    question_id: str,
    selected_option: str,
    is_correct: bool,
    confidence: str,
    shown_at: str | None,
    topic_id: str | None = None,
) -> dict:
    attempts = load_question_attempts(state_dir)
    events = load_attempt_events(state_dir)
    item = attempts.get(
        question_id,
        {"attempt_count": 0, "correct_count": 0, "difficulty": 0.5, "stability": 1.0},
    )
    now = datetime.now()
    response_time_ms = _response_ms(shown_at, now)
    base_interval = 3 if is_correct else 0
    confidence_adjust = {"low": -1, "medium": 0, "high": 2}.get(confidence, 0)
    next_due_days = max(0, base_interval + confidence_adjust)
    item["last_attempted_at"] = now.isoformat()
    item["last_selected_option"] = selected_option
    item["attempt_count"] = int(item.get("attempt_count", 0)) + 1
    item["correct_count"] = int(item.get("correct_count", 0)) + (1 if is_correct else 0)
    item["last_correct"] = is_correct
    item["last_confidence"] = confidence
    item["last_response_ms"] = response_time_ms
    item["difficulty"] = _bounded(
        float(item.get("difficulty", 0.5)) + (-0.07 if is_correct else 0.12),
        0.1,
        1.0,
    )
    item["stability"] = _bounded(
        float(item.get("stability", 1.0)) + (0.6 if is_correct else -0.4),
        0.2,
        30.0,
    )
    item["next_due"] = (date.today() + timedelta(days=next_due_days)).isoformat()
    attempts[question_id] = item
    save_question_attempts(state_dir, attempts)

    events.append(
        {
            "item_id": question_id,
            "item_type": "question",
            "topic_id": topic_id,
            "selected_option": selected_option,
            "confidence": confidence,
            "response_time_ms": response_time_ms,
            "is_correct": is_correct,
            "answered_at": now.isoformat(),
        }
    )
    save_attempt_events(state_dir, events)
    return item


def _response_ms(shown_at: str | None, now: datetime) -> int | None:
    if not shown_at:
        return None
    try:
        shown = datetime.fromisoformat(shown_at)
    except Exception:
        return None
    delta = int((now - shown).total_seconds() * 1000)
    return max(delta, 0)


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
