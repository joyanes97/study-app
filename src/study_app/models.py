from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


PRIORITY_FACTORS = {
    "low": 0.8,
    "medium": 1.0,
    "high": 1.2,
}


@dataclass
class Topic:
    id: str
    subject: str
    topic: str
    subtopic: str
    source_path: Path
    priority: str
    estimated_weight: float
    title: str
    body: str


@dataclass
class TopicProgress:
    topic_id: str
    mastery: float = 0.3
    forgetting_risk: float = 0.5
    last_seen: datetime | None = None
    generated_cards: int = 0
    generated_quiz_items: int = 0
    incorrect_streak: int = 0

    @property
    def weakness_factor(self) -> float:
        return max(0.2, 1.0 - self.mastery) + (self.incorrect_streak * 0.05)


@dataclass
class TopicScore:
    topic: Topic
    progress: TopicProgress
    score: float


@dataclass
class DailyPlan:
    plan_date: date
    exam_date: date
    days_left: int
    phase: str
    review_topics: list[TopicScore] = field(default_factory=list)
    weak_topics: list[TopicScore] = field(default_factory=list)
    new_topics: list[TopicScore] = field(default_factory=list)
    mixed_quiz_topics: list[TopicScore] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# Study plan for {self.plan_date.isoformat()}",
            "",
            f"- Exam date: {self.exam_date.isoformat()}",
            f"- Days left: {self.days_left}",
            f"- Phase: {self.phase}",
            "",
        ]
        sections = [
            ("Review topics", self.review_topics),
            ("Weak topics", self.weak_topics),
            ("New topics", self.new_topics),
            ("Mixed quiz", self.mixed_quiz_topics),
        ]
        for title, items in sections:
            lines.append(f"## {title}")
            if not items:
                lines.append("- none")
            else:
                for item in items:
                    lines.append(
                        f"- {item.topic.title} | score={item.score:.2f} | mastery={item.progress.mastery:.2f}"
                    )
            lines.append("")
        return "\n".join(lines).strip() + "\n"
