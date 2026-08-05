from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .learning import (
    CourseEnrollmentRead,
    CurriculumPathEnrollmentRead,
    LearnerProgressSummary,
    LearnerRead,
    LessonCompletionRead,
    LessonProgressRead,
)


class AcademyLearningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseEnrollmentRequest(BaseModel):
    course_id: int = Field(gt=0)


class PathEnrollmentRequest(BaseModel):
    curriculum_path_id: int = Field(gt=0)


class LessonProgressRequest(BaseModel):
    progress_percent: float | None = Field(default=None, ge=0, le=100)
    time_spent_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_update(self):
        if (
            self.progress_percent is None
            and self.time_spent_seconds is None
        ):
            raise ValueError("at least one progress field is required")
        return self


class LearnerAssessmentOption(AcademyLearningResponse):
    id: int
    option_text: str
    display_order: int


class LearnerAssessmentQuestion(AcademyLearningResponse):
    id: int
    question_type: str
    prompt: str
    points: float
    display_order: int
    options: list[LearnerAssessmentOption] = Field(default_factory=list)


class LearnerAssessmentDetail(AcademyLearningResponse):
    id: int
    title: str
    slug: str
    description: str | None
    assessment_type: str
    passing_score: float
    max_attempts: int | None
    time_limit_minutes: int | None
    questions: list[LearnerAssessmentQuestion] = Field(default_factory=list)


class StartAttemptResponse(AcademyLearningResponse):
    id: int
    assessment_id: int
    attempt_number: int
    status: str
    started_at: datetime


class AssessmentAnswerSubmission(BaseModel):
    question_id: int = Field(gt=0)
    selected_option_id: int | None = Field(default=None, gt=0)
    text_answer: str | None = Field(default=None, max_length=20000)


class SubmitAttemptRequest(BaseModel):
    answers: list[AssessmentAnswerSubmission]
    time_spent_seconds: int = Field(default=0, ge=0)


class LearnerAnswerResult(AcademyLearningResponse):
    id: int
    question_id: int
    selected_option_id: int | None
    text_answer: str | None
    grading_status: str
    is_correct: bool | None
    points_awarded: float | None
    manual_points_awarded: float | None = None
    manual_is_correct: bool | None = None
    feedback: str | None = None


class LearnerAttemptDetail(AcademyLearningResponse):
    id: int
    assessment_id: int
    attempt_number: int
    status: str
    grading_status: str
    started_at: datetime
    submitted_at: datetime | None
    score_percent: float | None
    points_earned: float | None
    points_possible: float | None
    passed: bool | None
    automatic_score_percent: float | None
    automatic_points_earned: float | None
    final_score_percent: float | None
    final_passed: bool | None
    answers: list[LearnerAnswerResult] = Field(default_factory=list)


class AttemptResultSummary(AcademyLearningResponse):
    attempt_id: int
    assessment_id: int
    grading_status: str
    provisional_score_percent: float | None
    provisional_passed: bool | None
    final_score_percent: float | None
    final_passed: bool | None
    points_earned: float | None
    points_possible: float | None


LearnerProfileResponse = LearnerRead
LearnerDashboardResponse = LearnerProgressSummary
CourseEnrollmentResponse = CourseEnrollmentRead
PathEnrollmentResponse = CurriculumPathEnrollmentRead
LessonProgressResponse = LessonProgressRead
LessonCompletionResponse = LessonCompletionRead


__all__ = [
    "AssessmentAnswerSubmission",
    "AttemptResultSummary",
    "CourseEnrollmentRequest",
    "CourseEnrollmentResponse",
    "LearnerAssessmentDetail",
    "LearnerAssessmentOption",
    "LearnerAssessmentQuestion",
    "LearnerAttemptDetail",
    "LearnerDashboardResponse",
    "LearnerProfileResponse",
    "LessonCompletionResponse",
    "LessonProgressRequest",
    "LessonProgressResponse",
    "PathEnrollmentRequest",
    "PathEnrollmentResponse",
    "StartAttemptResponse",
    "SubmitAttemptRequest",
]
