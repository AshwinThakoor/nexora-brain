from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar

from pydantic import Field, field_validator, model_validator

from ..models.enums import (
    AssessmentType,
    AttemptStatus,
    CompletionSource,
    EnrollmentStatus,
    LearnerStatus,
    LessonProgressStatus,
    QuestionType,
    GradingStatus,
)
from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    RequiredText,
    SlugString,
    TitleString,
)


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Percentage = Annotated[float, Field(ge=0.0, le=100.0)]
NonNegativePoints = Annotated[float, Field(ge=0.0)]


class LearnerBase(ORMResponse):
    external_user_id: NameString | None = None
    email: Annotated[str, Field(min_length=3, max_length=320)] | None = None
    display_name: NameString
    status: LearnerStatus = LearnerStatus.ACTIVE

    @field_validator("external_user_id", "email", mode="before")
    @classmethod
    def normalize_optional_identity(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None


class LearnerCreate(LearnerBase):
    @model_validator(mode="after")
    def require_identity(self):
        if self.external_user_id is None and self.email is None:
            raise ValueError("external_user_id or email is required")
        return self


class LearnerUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"display_name", "status"}
    )

    external_user_id: NameString | None = None
    email: Annotated[str, Field(min_length=3, max_length=320)] | None = None
    display_name: NameString | None = None
    status: LearnerStatus | None = None

    @field_validator("external_user_id", "email", mode="before")
    @classmethod
    def normalize_optional_identity(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None


class LearnerRead(LearnerBase):
    id: int
    created_at: datetime
    updated_at: datetime


class CourseEnrollmentBase(ORMResponse):
    learner_id: PositiveId
    course_id: PositiveId
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED
    enrolled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    progress_percent: Percentage = 0.0


class CourseEnrollmentCreate(CourseEnrollmentBase):
    pass


class CourseEnrollmentUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"status", "enrolled_at", "progress_percent"}
    )

    status: EnrollmentStatus | None = None
    enrolled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    progress_percent: Percentage | None = None


class CourseEnrollmentRead(CourseEnrollmentBase):
    id: int
    enrolled_at: datetime
    created_at: datetime
    updated_at: datetime


class CurriculumPathEnrollmentBase(ORMResponse):
    learner_id: PositiveId
    curriculum_path_id: PositiveId
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED
    enrolled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    progress_percent: Percentage = 0.0


class CurriculumPathEnrollmentCreate(CurriculumPathEnrollmentBase):
    pass


class CurriculumPathEnrollmentUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"status", "enrolled_at", "progress_percent"}
    )

    status: EnrollmentStatus | None = None
    enrolled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    progress_percent: Percentage | None = None


class CurriculumPathEnrollmentRead(CurriculumPathEnrollmentBase):
    id: int
    enrolled_at: datetime
    created_at: datetime
    updated_at: datetime


class LessonProgressBase(ORMResponse):
    learner_id: PositiveId
    lesson_id: PositiveId
    status: LessonProgressStatus = LessonProgressStatus.NOT_STARTED
    progress_percent: Percentage = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    time_spent_seconds: NonNegativeInt = 0
    attempt_count: NonNegativeInt = 0


class LessonProgressCreate(LessonProgressBase):
    pass


class LessonProgressUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "status",
            "progress_percent",
            "time_spent_seconds",
            "attempt_count",
        }
    )

    status: LessonProgressStatus | None = None
    progress_percent: Percentage | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    time_spent_seconds: NonNegativeInt | None = None
    attempt_count: NonNegativeInt | None = None


class LessonProgressRead(LessonProgressBase):
    id: int
    created_at: datetime
    updated_at: datetime


class LessonCompletionCreate(ORMResponse):
    learner_id: PositiveId
    lesson_id: PositiveId
    completed_at: datetime | None = None
    completion_source: CompletionSource = CompletionSource.MANUAL
    metadata_json: dict[str, Any] | list[Any] | None = None


class LessonCompletionRead(ORMResponse):
    id: int
    learner_id: int
    lesson_id: int
    completed_at: datetime
    completion_source: CompletionSource
    metadata_json: dict[str, Any] | list[Any] | None
    created_at: datetime


class AssessmentOptionBase(ORMResponse):
    option_text: RequiredText
    is_correct: bool = False
    display_order: NonNegativeInt = 0


class AssessmentOptionCreate(AssessmentOptionBase):
    question_id: PositiveId | None = None


class AssessmentOptionUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"option_text", "is_correct", "display_order"}
    )

    option_text: RequiredText | None = None
    is_correct: bool | None = None
    display_order: NonNegativeInt | None = None


class AssessmentOptionRead(AssessmentOptionBase):
    id: int
    question_id: int
    created_at: datetime
    updated_at: datetime


class AssessmentQuestionBase(ORMResponse):
    question_type: QuestionType
    prompt: RequiredText
    explanation: str | None = None
    points: NonNegativePoints = 1.0
    display_order: NonNegativeInt = 0
    metadata_json: dict[str, Any] | list[Any] | None = None


class AssessmentQuestionCreate(AssessmentQuestionBase):
    assessment_id: PositiveId | None = None
    options: list[AssessmentOptionCreate] = Field(default_factory=list)


class AssessmentQuestionUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"question_type", "prompt", "points", "display_order"}
    )

    question_type: QuestionType | None = None
    prompt: RequiredText | None = None
    explanation: str | None = None
    points: NonNegativePoints | None = None
    display_order: NonNegativeInt | None = None
    metadata_json: dict[str, Any] | list[Any] | None = None


class AssessmentQuestionRead(AssessmentQuestionBase):
    id: int
    assessment_id: int
    created_at: datetime
    updated_at: datetime
    options: list[AssessmentOptionRead] = Field(default_factory=list)


class AssessmentBase(ORMResponse):
    lesson_id: PositiveId | None = None
    module_id: PositiveId | None = None
    course_id: PositiveId | None = None
    title: TitleString
    slug: SlugString
    description: str | None = None
    assessment_type: AssessmentType = AssessmentType.QUIZ
    passing_score: Percentage = 70.0
    max_attempts: PositiveInt | None = None
    time_limit_minutes: PositiveInt | None = None
    is_active: bool = True
    display_order: NonNegativeInt = 0

    @model_validator(mode="after")
    def exactly_one_owner(self):
        if sum(
            value is not None
            for value in (self.lesson_id, self.module_id, self.course_id)
        ) != 1:
            raise ValueError(
                "exactly one of lesson_id, module_id, or course_id is required"
            )
        return self


class AssessmentCreate(AssessmentBase):
    questions: list[AssessmentQuestionCreate] = Field(default_factory=list)


class AssessmentUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "title",
            "slug",
            "assessment_type",
            "passing_score",
            "is_active",
            "display_order",
        }
    )

    lesson_id: PositiveId | None = None
    module_id: PositiveId | None = None
    course_id: PositiveId | None = None
    title: TitleString | None = None
    slug: SlugString | None = None
    description: str | None = None
    assessment_type: AssessmentType | None = None
    passing_score: Percentage | None = None
    max_attempts: PositiveInt | None = None
    time_limit_minutes: PositiveInt | None = None
    is_active: bool | None = None
    display_order: NonNegativeInt | None = None


class AssessmentRead(AssessmentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    questions: list[AssessmentQuestionRead] = Field(default_factory=list)


class AssessmentAnswerBase(ORMResponse):
    question_id: PositiveId
    selected_option_id: PositiveId | None = None
    text_answer: str | None = None


class AssessmentAnswerCreate(AssessmentAnswerBase):
    attempt_id: PositiveId | None = None


class AssessmentAnswerUpdate(PartialUpdateModel):
    selected_option_id: PositiveId | None = None
    text_answer: str | None = None
    is_correct: bool | None = None
    points_awarded: NonNegativePoints | None = None


class AssessmentAnswerRead(AssessmentAnswerBase):
    id: int
    attempt_id: int
    is_correct: bool | None
    points_awarded: float | None
    current_manual_grade_id: int | None = None
    grading_status: GradingStatus = GradingStatus.PENDING
    graded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AssessmentAttemptBase(ORMResponse):
    learner_id: PositiveId
    assessment_id: PositiveId
    attempt_number: PositiveInt
    status: AttemptStatus = AttemptStatus.IN_PROGRESS
    started_at: datetime
    submitted_at: datetime | None = None
    score_percent: Percentage | None = None
    points_earned: NonNegativePoints | None = None
    points_possible: NonNegativePoints | None = None
    passed: bool | None = None
    automatic_score_percent: Percentage | None = None
    automatic_points_earned: NonNegativePoints | None = None
    grading_status: GradingStatus = GradingStatus.PENDING
    reviewed_at: datetime | None = None
    final_score_percent: Percentage | None = None
    final_passed: bool | None = None
    time_spent_seconds: NonNegativeInt = 0


class AssessmentAttemptCreate(ORMResponse):
    learner_id: PositiveId
    assessment_id: PositiveId


class AssessmentAttemptUpdate(PartialUpdateModel):
    status: AttemptStatus | None = None
    submitted_at: datetime | None = None
    score_percent: Percentage | None = None
    points_earned: NonNegativePoints | None = None
    points_possible: NonNegativePoints | None = None
    passed: bool | None = None
    automatic_score_percent: Percentage | None = None
    automatic_points_earned: NonNegativePoints | None = None
    grading_status: GradingStatus | None = None
    reviewed_at: datetime | None = None
    final_score_percent: Percentage | None = None
    final_passed: bool | None = None
    time_spent_seconds: NonNegativeInt | None = None


class AssessmentAttemptRead(AssessmentAttemptBase):
    id: int
    created_at: datetime
    updated_at: datetime
    answers: list[AssessmentAnswerRead] = Field(default_factory=list)


class RecentActivityItem(ORMResponse):
    activity_type: str
    occurred_at: datetime
    lesson_id: int | None = None
    assessment_id: int | None = None
    detail: str | None = None


class AssessmentStatistics(ORMResponse):
    attempts_started: NonNegativeInt = 0
    attempts_submitted: NonNegativeInt = 0
    attempts_passed: NonNegativeInt = 0
    average_score_percent: Percentage | None = None


class CourseProgressSummary(ORMResponse):
    learner_id: int
    course_id: int
    enrollment_id: int | None = None
    status: EnrollmentStatus | None = None
    progress_percent: Percentage
    total_lessons: NonNegativeInt
    completed_lessons: NonNegativeInt
    time_spent_seconds: NonNegativeInt
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None


class PathProgressSummary(ORMResponse):
    learner_id: int
    curriculum_path_id: int
    enrollment_id: int | None = None
    status: EnrollmentStatus | None = None
    progress_percent: Percentage
    total_lessons: NonNegativeInt
    completed_lessons: NonNegativeInt
    time_spent_seconds: NonNegativeInt
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None


class LearnerProgressSummary(ORMResponse):
    learner: LearnerRead
    overall_progress_percent: Percentage
    course_enrollment_count: NonNegativeInt
    path_enrollment_count: NonNegativeInt
    completed_course_count: NonNegativeInt
    completed_path_count: NonNegativeInt
    completed_lesson_count: NonNegativeInt
    completion_event_count: NonNegativeInt
    total_time_spent_seconds: NonNegativeInt
    course_progress: list[CourseProgressSummary] = Field(default_factory=list)
    path_progress: list[PathProgressSummary] = Field(default_factory=list)
    recent_activity: list[RecentActivityItem] = Field(default_factory=list)
    assessment_statistics: AssessmentStatistics


LearnerResponse = LearnerRead
CourseEnrollmentResponse = CourseEnrollmentRead
CurriculumPathEnrollmentResponse = CurriculumPathEnrollmentRead
LessonProgressResponse = LessonProgressRead
LessonCompletionResponse = LessonCompletionRead
AssessmentResponse = AssessmentRead
AssessmentQuestionResponse = AssessmentQuestionRead
AssessmentOptionResponse = AssessmentOptionRead
AssessmentAttemptResponse = AssessmentAttemptRead
AssessmentAnswerResponse = AssessmentAnswerRead
CurriculumPathProgressSummary = PathProgressSummary


__all__ = [
    "AssessmentAnswerBase",
    "AssessmentAnswerCreate",
    "AssessmentAnswerRead",
    "AssessmentAnswerResponse",
    "AssessmentAnswerUpdate",
    "AssessmentAttemptBase",
    "AssessmentAttemptCreate",
    "AssessmentAttemptRead",
    "AssessmentAttemptResponse",
    "AssessmentAttemptUpdate",
    "AssessmentBase",
    "AssessmentCreate",
    "AssessmentOptionBase",
    "AssessmentOptionCreate",
    "AssessmentOptionRead",
    "AssessmentOptionResponse",
    "AssessmentOptionUpdate",
    "AssessmentQuestionBase",
    "AssessmentQuestionCreate",
    "AssessmentQuestionRead",
    "AssessmentQuestionResponse",
    "AssessmentQuestionUpdate",
    "AssessmentRead",
    "AssessmentResponse",
    "AssessmentStatistics",
    "AssessmentUpdate",
    "CourseEnrollmentBase",
    "CourseEnrollmentCreate",
    "CourseEnrollmentRead",
    "CourseEnrollmentResponse",
    "CourseEnrollmentUpdate",
    "CourseProgressSummary",
    "CurriculumPathEnrollmentBase",
    "CurriculumPathEnrollmentCreate",
    "CurriculumPathEnrollmentRead",
    "CurriculumPathEnrollmentResponse",
    "CurriculumPathEnrollmentUpdate",
    "CurriculumPathProgressSummary",
    "LearnerBase",
    "LearnerCreate",
    "LearnerProgressSummary",
    "LearnerRead",
    "LearnerResponse",
    "LearnerUpdate",
    "LessonCompletionCreate",
    "LessonCompletionRead",
    "LessonCompletionResponse",
    "LessonProgressBase",
    "LessonProgressCreate",
    "LessonProgressRead",
    "LessonProgressResponse",
    "LessonProgressUpdate",
    "PathProgressSummary",
    "RecentActivityItem",
]
