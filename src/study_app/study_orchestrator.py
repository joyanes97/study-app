from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from study_app.automation import run_automation
from study_app.contracts import (
    DailySessionRequest,
    ExamDateUpdateRequest,
    IngestPdfRequest,
    MockExamSubmission,
)
from study_app.pdf_ingest import ingest_pdf_inbox
from study_app.service import (
    build_dashboard_data,
    build_mock_exam_data,
    find_topic,
    next_card,
    next_question,
    next_session_item,
    progress_summary,
    score_mock_exam,
    update_exam_date,
)
from study_app.settings import load_settings


@dataclass
class StudyOrchestrator:
    root: Path

    def run_daily_cycle(self) -> dict[str, Any]:
        return run_automation(self.root)

    def dashboard(self, plan_date: date | None = None) -> dict[str, Any]:
        request = DailySessionRequest(plan_date=plan_date)
        return build_dashboard_data(self.root, request.plan_date or date.today())

    def topic_detail(self, topic_id: str) -> dict[str, Any] | None:
        return find_topic(topic_id, self.root)

    def study_card(self, topic_id: str | None = None) -> dict[str, Any] | None:
        return next_card(self.root, topic_id)

    def study_question(self, topic_id: str | None = None) -> dict[str, Any] | None:
        return next_question(self.root, topic_id)

    def study_session_item(self) -> dict[str, Any] | None:
        return next_session_item(self.root)

    def progress(self) -> dict[str, Any]:
        return progress_summary(self.root)

    def set_exam_date(self, exam_date: date) -> Path:
        request = ExamDateUpdateRequest(exam_date=exam_date)
        return update_exam_date(self.root, request.exam_date)

    def mock_exam(self) -> dict[str, Any]:
        return build_mock_exam_data(self.root)

    def score_exam(
        self, answers: dict[str, str], practical_text: str
    ) -> dict[str, Any]:
        request = MockExamSubmission(answers=answers, practical_text=practical_text)
        return score_mock_exam(self.root, request.answers, request.practical_text)

    def ingest_pdfs(self, source: str = "telegram") -> dict[str, Any]:
        request = IngestPdfRequest(source=source)
        settings = load_settings(self.root)
        return ingest_pdf_inbox(self.root, settings, self.root / "data" / "state")


def get_study_orchestrator(root: Path) -> StudyOrchestrator:
    return StudyOrchestrator(root=root)
