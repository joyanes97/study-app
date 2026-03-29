from __future__ import annotations

from datetime import date
from pathlib import Path

from study_app.markdown_loader import load_topics
from study_app.scheduler import build_daily_plan, score_topic
from study_app.settings import load_settings, save_exam_date
from study_app.state import load_progress, save_progress
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
    theory_topics = [topic for topic in topics if topic.content_type == "theory"]
    practical_topics = [topic for topic in topics if topic.content_type == "practical"]
    progress = load_progress(root / "data" / "state", topics)
    cards, questions = sync_generated_artifacts(
        root / "data" / "state", root / "data" / "generated", topics
    )
    card_reviews = load_card_reviews(root / "data" / "state")
    question_attempts = load_question_attempts(root / "data" / "state")
    progress = recalculate_progress(
        topics,
        progress,
        cards,
        questions,
        card_reviews,
        question_attempts,
    )
    save_progress(root / "data" / "state", progress)
    return (
        root,
        settings,
        topics,
        theory_topics,
        practical_topics,
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
        theory_topics,
        practical_topics,
        progress,
        cards,
        questions,
        card_reviews,
        question_attempts,
    ) = load_runtime(root)
    plan_date = plan_date or date.today()
    plan = build_daily_plan(theory_topics, progress, plan_date, settings)
    topic_rows = []
    practical_rows = []
    for topic in topics:
        topic_progress = progress[topic.id]
        item = {
            "id": topic.id,
            "content_type": topic.content_type,
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
        if topic.content_type == "practical":
            practical_rows.append(item)
        else:
            topic_rows.append(item)
    topic_rows.sort(key=lambda item: item["score"], reverse=True)
    practical_rows.sort(key=lambda item: item["score"], reverse=True)
    session_targets = calculate_session_targets(
        plan.days_left,
        plan.phase,
        len(cards),
        len(questions),
        practical_rows,
    )
    today_theory_cards = select_cards_for_today(
        plan, cards, card_reviews, session_targets["cards"]
    )
    today_theory_questions = select_questions_for_today(
        plan, questions, question_attempts, session_targets["questions"]
    )
    today_practical_cards = select_practical_cards(
        practical_rows, cards, card_reviews, session_targets["practical_cards"]
    )
    today_practical_questions = select_practical_questions(
        practical_rows,
        questions,
        question_attempts,
        session_targets["practical_questions"],
    )
    today_cards = today_theory_cards + today_practical_cards
    today_questions = today_theory_questions + today_practical_questions
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
        "topic_count": len(theory_topics),
        "practical_count": len(practical_topics),
        "card_count": len(cards),
        "question_count": len(questions),
        "topics": topic_rows,
        "practicals": practical_rows,
        "review_topics": [_topic_score_to_dict(item) for item in plan.review_topics],
        "weak_topics": [_topic_score_to_dict(item) for item in plan.weak_topics],
        "new_topics": [_topic_score_to_dict(item) for item in plan.new_topics],
        "mixed_quiz_topics": [
            _topic_score_to_dict(item) for item in plan.mixed_quiz_topics
        ],
        "today_theory_cards": today_theory_cards,
        "today_theory_questions": today_theory_questions,
        "today_practical_cards": today_practical_cards,
        "today_practical_questions": today_practical_questions,
        "today_cards": today_cards,
        "today_questions": today_questions,
        "study_queue": build_study_queue(today_cards, today_questions, daily_session),
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
    _, settings, topics, _, _, progress, cards, questions, _, _ = load_runtime(root)
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
    days_left: int,
    phase: str,
    card_pool: int,
    question_pool: int,
    practical_rows: list[dict],
) -> dict:
    if phase == "build":
        cards_target = 18
        questions_target = 8
        practical_cards_target = 0
        practical_questions_target = 0
    elif phase == "consolidate":
        cards_target = 14
        questions_target = 12
        practical_cards_target = 2 if practical_rows else 0
        practical_questions_target = 2 if practical_rows else 0
    else:
        cards_target = 10 if days_left <= 7 else 12
        questions_target = 16 if days_left <= 7 else 14
        practical_cards_target = 2 if practical_rows else 0
        practical_questions_target = 4 if practical_rows else 0

    cards_target = min(cards_target, card_pool)
    questions_target = min(questions_target, question_pool)

    if card_pool and cards_target == 0:
        cards_target = min(6, card_pool)
    if question_pool and questions_target == 0:
        questions_target = min(6, question_pool)

    return {
        "cards": cards_target,
        "questions": questions_target,
        "practical_cards": practical_cards_target,
        "practical_questions": practical_questions_target,
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


def _card_sort_key(card: dict, card_reviews: dict) -> tuple[int, str, float]:
    review = card_reviews.get(card["id"], {})
    next_due = review.get("next_due") or "1970-01-01"
    never_reviewed = 0 if review else -1
    difficulty = -float(review.get("difficulty", 0.5))
    return (never_reviewed, next_due, difficulty)


def select_questions_for_today(
    plan, questions: list[dict], attempts: dict, target_count: int
) -> list[dict]:
    topic_ids = {item.topic.id for item in (plan.weak_topics + plan.mixed_quiz_topics)}
    selected = [question for question in questions if question["topic_id"] in topic_ids]
    selected.sort(key=lambda question: _question_sort_key(question, attempts))
    return selected[:target_count]


def select_practical_cards(
    practical_rows: list[dict], cards: list[dict], card_reviews: dict, target_count: int
) -> list[dict]:
    if target_count <= 0:
        return []
    topic_ids = {item["id"] for item in practical_rows[:2]}
    selected = [card for card in cards if card["topic_id"] in topic_ids]
    selected.sort(key=lambda card: _card_sort_key(card, card_reviews))
    return selected[:target_count]


def select_practical_questions(
    practical_rows: list[dict],
    questions: list[dict],
    attempts: dict,
    target_count: int,
) -> list[dict]:
    if target_count <= 0:
        return []
    topic_ids = {item["id"] for item in practical_rows[:2]}
    selected = [question for question in questions if question["topic_id"] in topic_ids]
    selected.sort(key=lambda question: _question_sort_key(question, attempts))
    return selected[:target_count]


def _question_sort_key(question: dict, attempts: dict) -> tuple[int, int, str]:
    attempt = attempts.get(question["id"], {})
    correct_count = int(attempt.get("correct_count", 0))
    attempt_count = int(attempt.get("attempt_count", 0))
    next_due = attempt.get("next_due") or "1970-01-01"
    return (correct_count, attempt_count, next_due)


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


def next_session_item(root: Path | None = None):
    data = build_dashboard_data(root, date.today())
    queue = data["study_queue"]
    return queue[0] if queue else None


def build_study_queue(
    today_cards: list[dict], today_questions: list[dict], daily_session: dict
) -> list[dict]:
    done_cards = set(daily_session.get("completed_cards", []))
    done_questions = set(daily_session.get("completed_questions", []))
    pending_cards = [
        {"type": "card", "item": card, "content_type": _content_type_for_item(card)}
        for card in today_cards
        if card["id"] not in done_cards
    ]
    pending_questions = [
        {
            "type": "question",
            "item": question,
            "content_type": _content_type_for_item(question),
        }
        for question in today_questions
        if question["id"] not in done_questions
    ]
    queue = []
    max_len = max(len(pending_cards), len(pending_questions))
    for index in range(max_len):
        if index < len(pending_cards):
            queue.append(pending_cards[index])
        if index < len(pending_questions):
            queue.append(pending_questions[index])
    return queue


def _content_type_for_item(item: dict) -> str:
    return item.get("content_type", "theory")


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


def recalculate_progress(
    topics,
    progress,
    cards,
    questions,
    card_reviews,
    question_attempts,
):
    card_by_topic = {}
    for card in cards:
        card_by_topic.setdefault(card["topic_id"], []).append(card)
    question_by_topic = {}
    for question in questions:
        question_by_topic.setdefault(question["topic_id"], []).append(question)

    today = date.today().isoformat()
    for topic in topics:
        topic_cards = card_by_topic.get(topic.id, [])
        topic_questions = question_by_topic.get(topic.id, [])
        card_scores = []
        due_count = 0
        lapses = 0
        for card in topic_cards:
            review = card_reviews.get(card["id"], {})
            if not review:
                card_scores.append(0.2)
                due_count += 1
                continue
            rating_score = {"again": 0.1, "hard": 0.45, "good": 0.75, "easy": 0.9}.get(
                review.get("last_rating"), 0.4
            )
            confidence_score = {"low": -0.08, "medium": 0.0, "high": 0.06}.get(
                review.get("last_confidence"), 0.0
            )
            card_scores.append(max(0.0, min(1.0, rating_score + confidence_score)))
            if (review.get("next_due") or today) <= today:
                due_count += 1
            lapses += int(review.get("lapse_count", 0))

        question_scores = []
        incorrect_recent = 0
        for question in topic_questions:
            attempt = question_attempts.get(question["id"], {})
            attempt_count = int(attempt.get("attempt_count", 0))
            if attempt_count == 0:
                question_scores.append(0.2)
                due_count += 1
                continue
            accuracy = int(attempt.get("correct_count", 0)) / max(attempt_count, 1)
            confidence_bonus = {"low": -0.08, "medium": 0.0, "high": 0.06}.get(
                attempt.get("last_confidence"), 0.0
            )
            question_scores.append(max(0.0, min(1.0, accuracy + confidence_bonus)))
            if not attempt.get("last_correct", False):
                incorrect_recent += 1
            if (attempt.get("next_due") or today) <= today:
                due_count += 1

        scores = card_scores + question_scores
        mastery = sum(scores) / len(scores) if scores else 0.3
        total_items = max(len(topic_cards) + len(topic_questions), 1)
        due_ratio = due_count / total_items
        error_ratio = (
            incorrect_recent / max(len(topic_questions), 1) if topic_questions else 0.0
        )
        lapse_ratio = lapses / max(len(topic_cards), 1) if topic_cards else 0.0
        forgetting_risk = max(
            0.1,
            min(
                1.0,
                0.2
                + due_ratio * 0.45
                + error_ratio * 0.25
                + lapse_ratio * 0.2
                - mastery * 0.25,
            ),
        )

        topic_progress = progress[topic.id]
        topic_progress.mastery = round(mastery, 2)
        topic_progress.forgetting_risk = round(forgetting_risk, 2)
        topic_progress.generated_cards = len(topic_cards)
        topic_progress.generated_quiz_items = len(topic_questions)
        topic_progress.incorrect_streak = incorrect_recent
    return progress
