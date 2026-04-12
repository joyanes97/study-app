from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExamDateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_date: date


class DailySessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_date: date | None = None
    include_practicals: bool = True


class MockExamSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str] = Field(default_factory=dict)
    practical_text: str = ""


class IngestPdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["telegram", "manual"] = "telegram"
