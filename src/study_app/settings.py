from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class Settings:
    root: Path
    exam_date: date
    timezone: str
    daily_new_cards_limit: int
    daily_quiz_limit: int
    build_days: int
    consolidate_days: int
    reminder_hours: list[int]
    automation_scan_minutes: int
    telegram_media_dir: str
    pdf_inbox_dir: str
    pdf_text_min_chars: int
    pdf_max_pages: int
    glm_ocr_api_base: str
    glm_ocr_model: str
    default_topic_weight: float
    default_priority: str
    review_ratio: dict[str, float]


def load_settings(root: Path) -> Settings:
    config_path = root / "config" / "exam_config.json"
    data = json.loads(config_path.read_text())
    phase_boundaries = data.get("phase_boundaries", {})
    return Settings(
        root=root,
        exam_date=date.fromisoformat(data["exam_date"]),
        timezone=data.get("timezone", "UTC"),
        daily_new_cards_limit=int(data.get("daily_new_cards_limit", 30)),
        daily_quiz_limit=int(data.get("daily_quiz_limit", 20)),
        build_days=int(phase_boundaries.get("build_days", 60)),
        consolidate_days=int(phase_boundaries.get("consolidate_days", 21)),
        reminder_hours=[int(hour) for hour in data.get("reminder_hours", [14, 19, 22])],
        automation_scan_minutes=int(data.get("automation_scan_minutes", 15)),
        telegram_media_dir=data.get(
            "telegram_media_dir", "/home/jose/.nanobot-study/media/telegram"
        ),
        pdf_inbox_dir=data.get(
            "pdf_inbox_dir", str(root / "data" / "content" / "inbox")
        ),
        pdf_text_min_chars=int(data.get("pdf_text_min_chars", 800)),
        pdf_max_pages=int(data.get("pdf_max_pages", 20)),
        glm_ocr_api_base=data.get("glm_ocr_api_base", "http://192.168.3.25:8081/v1"),
        glm_ocr_model=data.get("glm_ocr_model", "glm-ocr"),
        default_topic_weight=float(data.get("default_topic_weight", 0.5)),
        default_priority=data.get("default_priority", "medium"),
        review_ratio=data.get(
            "review_ratio", {"build": 0.5, "consolidate": 0.6, "final": 0.7}
        ),
    )
