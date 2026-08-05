from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


Reason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class GradingORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GradeShortAnswerRequest(BaseModel):
    points_awarded: float = Field(ge=0)
    is_correct: bool | None = None
    feedback: str | None = Field(default=None, max_length=10000)
    grading_reason: str | None = Field(default=None, max_length=4000)


class ChangeGradeRequest(GradeShortAnswerRequest):
    grading_reason: Reason


class ManualGradeResponse(GradingORMResponse):
    id: int
    assessment_answer_id: int
    grader_external_id: str | None
    grader_role: str
    points_awarded: float
    is_correct: bool | None
    feedback: str | None
    grading_reason: str | None
    created_at: datetime


class ReviewRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=10000)


class ReviewDecisionRequest(BaseModel):
    reason: Reason
    notes: str | None = Field(default=None, max_length=10000)


class AssessmentReviewResponse(GradingORMResponse):
    id: int
    assessment_attempt_id: int
    reviewer_external_id: str | None
    review_status: str
    review_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class RegradeAnswerRequest(BaseModel):
    assessment_answer_id: int = Field(gt=0)
    points_awarded: float = Field(ge=0)
    is_correct: bool | None = None
    feedback: str | None = Field(default=None, max_length=10000)


class RegradeAttemptRequest(BaseModel):
    reason: Reason
    grades: list[RegradeAnswerRequest]
    notes: str | None = Field(default=None, max_length=10000)


class GradingAuditEventResponse(GradingORMResponse):
    id: int
    assessment_attempt_id: int
    assessment_answer_id: int | None
    actor_external_id: str | None
    actor_role: str
    event_type: str
    previous_values_json: dict[str, Any] | list[Any] | None
    new_values_json: dict[str, Any] | list[Any] | None
    reason: str | None
    created_at: datetime


class AttemptGradingSummary(GradingORMResponse):
    id: int
    learner_id: int
    assessment_id: int
    attempt_number: int
    status: str
    grading_status: str
    submitted_at: datetime | None
    score_percent: float | None
    final_score_percent: float | None
    final_passed: bool | None


class GradingHistoryResponse(BaseModel):
    grades: list[ManualGradeResponse]
    audit_events: list[GradingAuditEventResponse]


__all__ = [
    "AssessmentReviewResponse",
    "AttemptGradingSummary",
    "ChangeGradeRequest",
    "GradeShortAnswerRequest",
    "GradingAuditEventResponse",
    "GradingHistoryResponse",
    "ManualGradeResponse",
    "RegradeAnswerRequest",
    "RegradeAttemptRequest",
    "ReviewDecisionRequest",
    "ReviewRequest",
]
