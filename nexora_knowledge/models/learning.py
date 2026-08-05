from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin, utc_now
from .enums import (
    AssessmentType,
    AttemptStatus,
    CompletionSource,
    EnrollmentStatus,
    GradingStatus,
    LearnerStatus,
    LessonProgressStatus,
)


class Learner(TimestampMixin, Base):
    __tablename__ = "learners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_user_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(320),
        unique=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=LearnerStatus.ACTIVE.value,
    )

    course_enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        "CourseEnrollment",
        back_populates="learner",
        order_by="CourseEnrollment.enrolled_at",
    )
    curriculum_path_enrollments: Mapped[
        list["CurriculumPathEnrollment"]
    ] = relationship(
        "CurriculumPathEnrollment",
        back_populates="learner",
        order_by="CurriculumPathEnrollment.enrolled_at",
    )
    lesson_progress_records: Mapped[list["LessonProgress"]] = relationship(
        "LessonProgress",
        back_populates="learner",
        order_by="LessonProgress.id",
    )
    completion_events: Mapped[list["LessonCompletion"]] = relationship(
        "LessonCompletion",
        back_populates="learner",
        order_by="LessonCompletion.completed_at",
    )
    assessment_attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        "AssessmentAttempt",
        back_populates="learner",
        order_by="AssessmentAttempt.started_at",
    )


class CourseEnrollment(TimestampMixin, Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "course_id",
            name="uq_course_enrollment_learner_course",
        ),
        CheckConstraint(
            "progress_percent >= 0.0 AND progress_percent <= 100.0",
            name="ck_course_enrollments_progress_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=EnrollmentStatus.ENROLLED.value,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    progress_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    learner: Mapped[Learner] = relationship(
        "Learner",
        back_populates="course_enrollments",
    )
    course: Mapped["Course"] = relationship("Course")


class CurriculumPathEnrollment(TimestampMixin, Base):
    __tablename__ = "curriculum_path_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "curriculum_path_id",
            name="uq_path_enrollment_learner_path",
        ),
        CheckConstraint(
            "progress_percent >= 0.0 AND progress_percent <= 100.0",
            name="ck_path_enrollments_progress_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    curriculum_path_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_paths.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=EnrollmentStatus.ENROLLED.value,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    progress_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    learner: Mapped[Learner] = relationship(
        "Learner",
        back_populates="curriculum_path_enrollments",
    )
    curriculum_path: Mapped["CurriculumPath"] = relationship(
        "CurriculumPath"
    )


class LessonProgress(TimestampMixin, Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "lesson_id",
            name="uq_lesson_progress_learner_lesson",
        ),
        CheckConstraint(
            "progress_percent >= 0.0 AND progress_percent <= 100.0",
            name="ck_lesson_progress_percent_range",
        ),
        CheckConstraint(
            "time_spent_seconds >= 0",
            name="ck_lesson_progress_time_nonnegative",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_lesson_progress_attempts_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=LessonProgressStatus.NOT_STARTED.value,
    )
    progress_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    time_spent_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    learner: Mapped[Learner] = relationship(
        "Learner",
        back_populates="lesson_progress_records",
    )
    lesson: Mapped["Lesson"] = relationship("Lesson")


class LessonCompletion(CreatedAtMixin, Base):
    __tablename__ = "lesson_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    completion_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CompletionSource.MANUAL.value,
    )
    metadata_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )

    learner: Mapped[Learner] = relationship(
        "Learner",
        back_populates="completion_events",
    )
    lesson: Mapped["Lesson"] = relationship("Lesson")


class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "("
            "(lesson_id IS NOT NULL AND module_id IS NULL "
            "AND course_id IS NULL) OR "
            "(lesson_id IS NULL AND module_id IS NOT NULL "
            "AND course_id IS NULL) OR "
            "(lesson_id IS NULL AND module_id IS NULL "
            "AND course_id IS NOT NULL)"
            ")",
            name="ck_assessments_exactly_one_owner",
        ),
        CheckConstraint(
            "passing_score >= 0.0 AND passing_score <= 100.0",
            name="ck_assessments_passing_score_range",
        ),
        CheckConstraint(
            "max_attempts IS NULL OR max_attempts > 0",
            name="ck_assessments_max_attempts_positive",
        ),
        CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes > 0",
            name="ck_assessments_time_limit_positive",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_assessments_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="RESTRICT"),
        index=True,
    )
    module_id: Mapped[int | None] = mapped_column(
        ForeignKey("modules.id", ondelete="RESTRICT"),
        index=True,
    )
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    assessment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AssessmentType.QUIZ.value,
    )
    passing_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=70.0,
    )
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    lesson: Mapped["Lesson | None"] = relationship(
        "Lesson",
        foreign_keys=[lesson_id],
    )
    module: Mapped["Module | None"] = relationship(
        "Module",
        foreign_keys=[module_id],
    )
    course: Mapped["Course | None"] = relationship(
        "Course",
        foreign_keys=[course_id],
    )
    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        "AssessmentQuestion",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="(AssessmentQuestion.display_order, AssessmentQuestion.id)",
    )
    attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        "AssessmentAttempt",
        back_populates="assessment",
        order_by="AssessmentAttempt.attempt_number",
    )


class AssessmentQuestion(TimestampMixin, Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        CheckConstraint(
            "points >= 0.0",
            name="ck_assessment_questions_points_nonnegative",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_assessment_questions_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    metadata_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )

    assessment: Mapped[Assessment] = relationship(
        "Assessment",
        back_populates="questions",
    )
    options: Mapped[list["AssessmentOption"]] = relationship(
        "AssessmentOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="(AssessmentOption.display_order, AssessmentOption.id)",
    )


class AssessmentOption(TimestampMixin, Base):
    __tablename__ = "assessment_options"
    __table_args__ = (
        CheckConstraint(
            "display_order >= 0",
            name="ck_assessment_options_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    question: Mapped[AssessmentQuestion] = relationship(
        "AssessmentQuestion",
        back_populates="options",
    )


class AssessmentAttempt(TimestampMixin, Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "assessment_id",
            "attempt_number",
            name="uq_assessment_attempt_number",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_assessment_attempt_number_positive",
        ),
        CheckConstraint(
            "time_spent_seconds >= 0",
            name="ck_assessment_attempt_time_nonnegative",
        ),
        CheckConstraint(
            "score_percent IS NULL OR "
            "(score_percent >= 0.0 AND score_percent <= 100.0)",
            name="ck_assessment_attempt_score_range",
        ),
        CheckConstraint(
            "points_earned IS NULL OR points_earned >= 0.0",
            name="ck_assessment_attempt_points_earned_nonnegative",
        ),
        CheckConstraint(
            "points_possible IS NULL OR points_possible >= 0.0",
            name="ck_assessment_attempt_points_possible_nonnegative",
        ),
        CheckConstraint(
            "automatic_score_percent IS NULL OR "
            "(automatic_score_percent >= 0.0 "
            "AND automatic_score_percent <= 100.0)",
            name="ck_attempt_automatic_score_range",
        ),
        CheckConstraint(
            "automatic_points_earned IS NULL "
            "OR automatic_points_earned >= 0.0",
            name="ck_attempt_automatic_points_nonnegative",
        ),
        CheckConstraint(
            "final_score_percent IS NULL OR "
            "(final_score_percent >= 0.0 AND final_score_percent <= 100.0)",
            name="ck_assessment_attempt_final_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AttemptStatus.IN_PROGRESS.value,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    score_percent: Mapped[float | None] = mapped_column(Float)
    points_earned: Mapped[float | None] = mapped_column(Float)
    points_possible: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    automatic_score_percent: Mapped[float | None] = mapped_column(Float)
    automatic_points_earned: Mapped[float | None] = mapped_column(Float)
    grading_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=GradingStatus.PENDING.value,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    final_score_percent: Mapped[float | None] = mapped_column(Float)
    final_passed: Mapped[bool | None] = mapped_column(Boolean)
    time_spent_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    learner: Mapped[Learner] = relationship(
        "Learner",
        back_populates="assessment_attempts",
    )
    assessment: Mapped[Assessment] = relationship(
        "Assessment",
        back_populates="attempts",
    )
    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        "AssessmentAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AssessmentAnswer.id",
    )
    review: Mapped["AssessmentReview | None"] = relationship(
        "AssessmentReview",
        back_populates="attempt",
        uselist=False,
    )
    grading_audit_events: Mapped[list["GradingAuditEvent"]] = relationship(
        "GradingAuditEvent",
        back_populates="attempt",
        order_by="GradingAuditEvent.id",
    )


class AssessmentAnswer(TimestampMixin, Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_assessment_answer_attempt_question",
        ),
        CheckConstraint(
            "points_awarded IS NULL OR points_awarded >= 0.0",
            name="ck_assessment_answers_points_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    selected_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessment_options.id", ondelete="RESTRICT"),
        index=True,
    )
    text_answer: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    points_awarded: Mapped[float | None] = mapped_column(Float)
    current_manual_grade_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "manual_grades.id",
            name="fk_answers_current_manual_grade",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        index=True,
    )
    grading_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=GradingStatus.PENDING.value,
    )
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attempt: Mapped[AssessmentAttempt] = relationship(
        "AssessmentAttempt",
        back_populates="answers",
    )
    question: Mapped[AssessmentQuestion] = relationship(
        "AssessmentQuestion"
    )
    selected_option: Mapped[AssessmentOption | None] = relationship(
        "AssessmentOption"
    )
    current_manual_grade: Mapped["ManualGrade | None"] = relationship(
        "ManualGrade",
        foreign_keys=[current_manual_grade_id],
        post_update=True,
    )
    manual_grades: Mapped[list["ManualGrade"]] = relationship(
        "ManualGrade",
        foreign_keys="ManualGrade.assessment_answer_id",
        back_populates="answer",
        order_by="ManualGrade.id",
    )


__all__ = [
    "Assessment",
    "AssessmentAnswer",
    "AssessmentAttempt",
    "AssessmentOption",
    "AssessmentQuestion",
    "CourseEnrollment",
    "CurriculumPathEnrollment",
    "Learner",
    "LessonCompletion",
    "LessonProgress",
]
