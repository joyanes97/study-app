from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path

from study_app.markdown_loader import load_topics
from study_app.scheduler import build_daily_plan, score_topic
from study_app.settings import Settings, load_settings
from study_app.state import load_progress


def get_root() -> Path:
    return Path('/home/jose/exam-study-app')


def load_runtime(root: Path | None = None):
    root = root or get_root()
    settings = load_settings(root)
    topics = load_topics(root / 'data' / 'content', settings.default_priority, settings.default_topic_weight)
    progress = load_progress(root / 'data' / 'state', topics)
    return root, settings, topics, progress


def phase_for_date(settings: Settings, plan_date: date) -> str:
    return build_daily_plan([], {}, plan_date, settings).phase


def build_dashboard_data(root: Path | None = None, plan_date: date | None = None) -> dict:
    root, settings, topics, progress = load_runtime(root)
    plan_date = plan_date or date.today()
    plan = build_daily_plan(topics, progress, plan_date, settings)
    topic_rows = []
    for topic in topics:
        topic_progress = progress[topic.id]
        topic_rows.append({
            'id': topic.id,
            'subject': topic.subject,
            'topic': topic.topic,
            'subtopic': topic.subtopic,
            'title': topic.title,
            'path': str(topic.source_path),
            'priority': topic.priority,
            'estimated_weight': topic.estimated_weight,
            'mastery': topic_progress.mastery,
            'forgetting_risk': topic_progress.forgetting_risk,
            'generated_cards': topic_progress.generated_cards,
            'generated_quiz_items': topic_progress.generated_quiz_items,
            'score': score_topic(topic, topic_progress, plan.days_left),
        })
    topic_rows.sort(key=lambda item: item['score'], reverse=True)
    return {
        'root': str(root),
        'exam_date': settings.exam_date.isoformat(),
        'plan_date': plan.plan_date.isoformat(),
        'days_left': plan.days_left,
        'phase': plan.phase,
        'today_plan_markdown': plan.to_markdown(),
        'topic_count': len(topics),
        'topics': topic_rows,
        'review_topics': [_topic_score_to_dict(item) for item in plan.review_topics],
        'weak_topics': [_topic_score_to_dict(item) for item in plan.weak_topics],
        'new_topics': [_topic_score_to_dict(item) for item in plan.new_topics],
        'mixed_quiz_topics': [_topic_score_to_dict(item) for item in plan.mixed_quiz_topics],
    }


def _topic_score_to_dict(item) -> dict:
    return {
        'id': item.topic.id,
        'title': item.topic.title,
        'subject': item.topic.subject,
        'priority': item.topic.priority,
        'estimated_weight': item.topic.estimated_weight,
        'score': round(item.score, 2),
        'mastery': round(item.progress.mastery, 2),
        'forgetting_risk': round(item.progress.forgetting_risk, 2),
        'generated_cards': item.progress.generated_cards,
        'generated_quiz_items': item.progress.generated_quiz_items,
        'path': str(item.topic.source_path),
    }


def find_topic(topic_id: str, root: Path | None = None):
    _, settings, topics, progress = load_runtime(root)
    for topic in topics:
        if topic.id == topic_id:
            topic_progress = progress[topic.id]
            return {
                'topic': topic,
                'progress': topic_progress,
                'settings': settings,
            }
    return None
