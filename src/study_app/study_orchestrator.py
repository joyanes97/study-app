from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from study_app.automation import run_automation
from study_app.service import (
    build_dashboard_data,
    build_mock_exam_data,
    score_mock_exam,
)


@dataclass
class StudyOrchestrator:
    root: Path

    def run_daily_cycle(self) -> dict[str, Any]:
        return run_automation(self.root)

    def dashboard(self, plan_date: date | None = None) -> dict[str, Any]:
        return build_dashboard_data(self.root, plan_date or date.today())

    def mock_exam(self) -> dict[str, Any]:
        return build_mock_exam_data(self.root)

    def score_exam(
        self, answers: dict[str, str], practical_text: str
    ) -> dict[str, Any]:
        return score_mock_exam(self.root, answers, practical_text)


def get_study_orchestrator(root: Path) -> StudyOrchestrator:
    return StudyOrchestrator(root=root)
