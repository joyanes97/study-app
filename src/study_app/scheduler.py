from __future__ import annotations

from datetime import date

from study_app.models import DailyPlan, PRIORITY_FACTORS, Topic, TopicScore, TopicProgress
from study_app.settings import Settings


def determine_phase(days_left: int, settings: Settings) -> str:
    if days_left > settings.build_days:
        return "build"
    if days_left > settings.consolidate_days:
        return "consolidate"
    return "final"


def score_topic(topic: Topic, progress: TopicProgress, days_left: int) -> float:
    priority_factor = PRIORITY_FACTORS.get(topic.priority, 1.0)
    time_pressure = 1.0 + max(0, 30 - max(days_left, 0)) / 30
    card_gap = 1.15 if progress.generated_cards == 0 else 1.0
    quiz_gap = 1.10 if progress.generated_quiz_items == 0 else 1.0
    return (
        topic.estimated_weight
        * priority_factor
        * progress.weakness_factor
        * max(0.3, progress.forgetting_risk)
        * time_pressure
        * card_gap
        * quiz_gap
    )


def build_daily_plan(
    topics: list[Topic],
    progress: dict[str, TopicProgress],
    plan_date: date,
    settings: Settings,
) -> DailyPlan:
    days_left = (settings.exam_date - plan_date).days
    phase = determine_phase(days_left, settings)
    scored = [
        TopicScore(topic=topic, progress=progress[topic.id], score=score_topic(topic, progress[topic.id], days_left))
        for topic in topics
    ]
    scored.sort(key=lambda item: item.score, reverse=True)

    reviews = [item for item in scored if item.progress.forgetting_risk >= 0.55][:6]
    weak = [item for item in scored if item.progress.mastery <= 0.45][:5]
    new_topics = [item for item in scored if item.progress.generated_cards == 0][:4]
    mixed_quiz = scored[: max(1, min(len(scored), settings.daily_quiz_limit // 5))]

    if phase == "final":
        new_topics = new_topics[:1]
        reviews = reviews[:8]
        mixed_quiz = scored[:6]
    elif phase == "build":
        new_topics = new_topics[:4]
        mixed_quiz = scored[:3]

    return DailyPlan(
        plan_date=plan_date,
        exam_date=settings.exam_date,
        days_left=days_left,
        phase=phase,
        review_topics=reviews,
        weak_topics=weak,
        new_topics=new_topics,
        mixed_quiz_topics=mixed_quiz,
    )
