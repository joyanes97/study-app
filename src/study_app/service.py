from __future__ import annotations

from datetime import date
from pathlib import Path

from study_app.markdown_loader import load_topics
from study_app.scheduler import build_daily_plan, score_topic
from study_app.settings import load_settings, save_exam_date
from study_app.state import load_progress
from study_app.study_store import (
    ensure_daily_session,
    load_automation_report,
    load_card_reviews,
    load_cards,
    load_daily_sessions,
    load_question_attempts,
    load_questions,
    sync_generated_artifacts,
    update_daily_session_completion,
)
from study_app.targets import estimate_target_cards, estimate_target_questions


def get_root() -> Path:
    return Path("/home/jose/exam-study-app")


def load_runtime(root: Path | None = None):
    root = root or get_root()
    settings = load_settings(root)
    topics = load_topics(
        root / "data" / "content",
        settings.default_priority,
        settings.default_topic_weight,
    )
    progress = load_progress(root / "data" / "state", topics)
    cards, questions = sync_generated_artifacts(
        root / "data" / "state", root / "data" / "generated", topics
    )
    card_reviews = load_card_reviews(root / "data" / "state")
    question_attempts = load_question_attempts(root / "data" / "state")
    return (
        root,
        settings,
        topics,
        progress,
        cards,
        questions,
        card_reviews,
        question_attempts,
    )


def build_dashboard_data(
    root: Path | None = None, plan_date: date | None = None
) -> dict:
    (
        root,
        settings,
        topics,
        progress,
        cards,
        questions,
        card_reviews,
        question_attempts,
    ) = load_runtime(root)
    plan_date = plan_date or date.today()
    plan = build_daily_plan(topics, progress, plan_date, settings)
    topic_rows = []
    for topic in topics:
        topic_progress = progress[topic.id]
        topic_rows.append(
            {
                "id": topic.id,
                "subject": topic.subject,
                "topic": topic.topic,
                "subtopic": topic.subtopic,
                "title": topic.title,
                "path": str(topic.source_path),
                "priority": topic.priority,
                "estimated_weight": topic.estimated_weight,
                "mastery": topic_progress.mastery,
                "forgetting_risk": topic_progress.forgetting_risk,
                "generated_cards": topic_progress.generated_cards,
                "generated_quiz_items": topic_progress.generated_quiz_items,
                "target_cards": estimate_target_cards(topic.title, topic.body),
                "target_questions": estimate_target_questions(topic.title, topic.body),
                "score": score_topic(topic, topic_progress, plan.days_left),
            }
        )
    topic_rows.sort(key=lambda item: item["score"], reverse=True)
    session_targets = calculate_session_targets(
        plan.days_left, plan.phase, len(cards), len(questions)
    )
    today_cards = select_cards_for_today(
        plan, cards, card_reviews, session_targets["cards"]
    )
    today_questions = select_questions_for_today(
        plan, questions, question_attempts, session_targets["questions"]
    )
    daily_session = ensure_daily_session(
        root / "data" / "state", plan_date, today_cards, today_questions
    )
    automation_report = load_automation_report(root / "data" / "state")
    return {
        "root": str(root),
        "exam_date": settings.exam_date.isoformat(),
        "plan_date": plan.plan_date.isoformat(),
        "days_left": plan.days_left,
        "phase": plan.phase,
        "today_plan_markdown": plan.to_markdown(),
        "topic_count": len(topics),
        "card_count": len(cards),
        "question_count": len(questions),
        "topics": topic_rows,
        "review_topics": [_topic_score_to_dict(item) for item in plan.review_topics],
        "weak_topics": [_topic_score_to_dict(item) for item in plan.weak_topics],
        "new_topics": [_topic_score_to_dict(item) for item in plan.new_topics],
        "mixed_quiz_topics": [
            _topic_score_to_dict(item) for item in plan.mixed_quiz_topics
        ],
        "today_cards": today_cards,
        "today_questions": today_questions,
        "session_targets": session_targets,
        "daily_session": daily_session,
        "automation_report": automation_report,
    }


def _topic_score_to_dict(item) -> dict:
    return {
        "id": item.topic.id,
        "title": item.topic.title,
        "subject": item.topic.subject,
        "priority": item.topic.priority,
        "estimated_weight": item.topic.estimated_weight,
        "score": round(item.score, 2),
        "mastery": round(item.progress.mastery, 2),
        "forgetting_risk": round(item.progress.forgetting_risk, 2),
        "generated_cards": item.progress.generated_cards,
        "generated_quiz_items": item.progress.generated_quiz_items,
        "target_cards": estimate_target_cards(item.topic.title, item.topic.body),
        "target_questions": estimate_target_questions(
            item.topic.title, item.topic.body
        ),
        "path": str(item.topic.source_path),
    }


def find_topic(topic_id: str, root: Path | None = None):
    _, settings, topics, progress, cards, questions, _, _ = load_runtime(root)
    for topic in topics:
        if topic.id == topic_id:
            topic_progress = progress[topic.id]
            return {
                "topic": topic,
                "progress": topic_progress,
                "settings": settings,
                "cards": [card for card in cards if card["topic_id"] == topic_id],
                "questions": [
                    question
                    for question in questions
                    if question["topic_id"] == topic_id
                ],
            }
    return None


def calculate_session_targets(
    days_left: int, phase: str, card_pool: int, question_pool: int
) -> dict:
    if phase == "build":
        cards_target = 18
        questions_target = 8
    elif phase == "consolidate":
        cards_target = 14
        questions_target = 12
    else:
        cards_target = 10 if days_left <= 7 else 12
        questions_target = 16 if days_left <= 7 else 14

    cards_target = min(cards_target, card_pool)
    questions_target = min(questions_target, question_pool)

    if card_pool and cards_target == 0:
        cards_target = min(6, card_pool)
    if question_pool and questions_target == 0:
        questions_target = min(6, question_pool)

    return {
        "cards": cards_target,
        "questions": questions_target,
    }


def select_cards_for_today(
    plan, cards: list[dict], card_reviews: dict, target_count: int
) -> list[dict]:
    topic_ids = {
        item.topic.id
        for item in (plan.review_topics + plan.weak_topics + plan.new_topics)
    }
    selected = [card for card in cards if card["topic_id"] in topic_ids]
    selected.sort(key=lambda card: _card_sort_key(card, card_reviews))
    return selected[:target_count]


def _card_sort_key(card: dict, card_reviews: dict) -> tuple[int, str]:
    review = card_reviews.get(card["id"], {})
    next_due = review.get("next_due") or "1970-01-01"
    never_reviewed = 0 if review else -1
    return (never_reviewed, next_due)


def select_questions_for_today(
    plan, questions: list[dict], attempts: dict, target_count: int
) -> list[dict]:
    topic_ids = {item.topic.id for item in (plan.weak_topics + plan.mixed_quiz_topics)}
    selected = [question for question in questions if question["topic_id"] in topic_ids]
    selected.sort(key=lambda question: _question_sort_key(question, attempts))
    return selected[:target_count]


def _question_sort_key(question: dict, attempts: dict) -> tuple[int, int]:
    attempt = attempts.get(question["id"], {})
    correct_count = int(attempt.get("correct_count", 0))
    attempt_count = int(attempt.get("attempt_count", 0))
    return (correct_count, attempt_count)


def next_card(root: Path | None = None, topic_id: str | None = None):
    data = build_dashboard_data(root, date.today())
    cards = data["today_cards"]
    if topic_id:
        cards = [card for card in cards if card["topic_id"] == topic_id]
    done = set(data["daily_session"].get("completed_cards", []))
    for card in cards:
        if card["id"] not in done:
            return card
    return cards[0] if cards else None


def next_question(root: Path | None = None, topic_id: str | None = None):
    data = build_dashboard_data(root, date.today())
    questions = data["today_questions"]
    if topic_id:
        questions = [
            question for question in questions if question["topic_id"] == topic_id
        ]
    done = set(data["daily_session"].get("completed_questions", []))
    for question in questions:
        if question["id"] not in done:
            return question
    return questions[0] if questions else None


def mark_session_item_complete(root: Path, item_type: str, item_id: str) -> dict:
    return update_daily_session_completion(
        root / "data" / "state", date.today(), item_type, item_id
    )


def progress_summary(root: Path | None = None) -> dict:
    root = root or get_root()
    data = build_dashboard_data(root, date.today())
    sessions = load_daily_sessions(root / "data" / "state")
    return {
        "daily_session": data["daily_session"],
        "topics": data["topics"],
        "cards": data["card_count"],
        "questions": data["question_count"],
        "sessions": sessions,
        "automation_report": data["automation_report"],
    }


def update_exam_date(root: Path | None, new_exam_date: date) -> Path:
    root = root or get_root()
    return save_exam_date(root, new_exam_date)
