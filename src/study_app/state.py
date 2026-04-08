from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from study_app.models import Topic, TopicProgress
from study_app.study_sqlite import get_study_store


def load_progress(state_dir: Path, topics: list[Topic]) -> dict[str, TopicProgress]:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "progress.json"
    store = get_study_store(state_dir)
    raw = store.load_mapping("progress", "topic_id")
    if not raw:
        raw = json.loads(path.read_text()) if path.exists() else {}
        if raw:
            store.save_mapping("progress", "topic_id", raw)
    progress: dict[str, TopicProgress] = {}
    for topic in topics:
        item = raw.get(topic.id, {})
        last_seen = item.get("last_seen")
        progress[topic.id] = TopicProgress(
            topic_id=topic.id,
            mastery=float(item.get("mastery", 0.3)),
            forgetting_risk=float(item.get("forgetting_risk", 0.5)),
            last_seen=datetime.fromisoformat(last_seen) if last_seen else None,
            generated_cards=int(item.get("generated_cards", 0)),
            generated_quiz_items=int(item.get("generated_quiz_items", 0)),
            incorrect_streak=int(item.get("incorrect_streak", 0)),
        )
    return progress


def save_progress(state_dir: Path, progress: dict[str, TopicProgress]) -> Path:
    path = state_dir / "progress.json"
    serialized = {
        key: {
            "mastery": value.mastery,
            "forgetting_risk": value.forgetting_risk,
            "last_seen": value.last_seen.isoformat() if value.last_seen else None,
            "generated_cards": value.generated_cards,
            "generated_quiz_items": value.generated_quiz_items,
            "incorrect_streak": value.incorrect_streak,
        }
        for key, value in progress.items()
    }
    store = get_study_store(state_dir)
    store.save_mapping("progress", "topic_id", serialized)
    path.write_text(json.dumps(serialized, indent=2) + "\n", encoding="utf-8")
    return path
