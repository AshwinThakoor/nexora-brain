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
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin
from .enums import AssessmentReviewStatus


class ManualGrade(CreatedAtMixin, Base):
    """An append-only manual grading decision for one submitted answer."""

    __tablename__ = "manual_grades"
    __table_args__ = (
        CheckConstraint(
            "points_awarded >= 0.0",
            name="ck_manual_grades_points_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_answer_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_answers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    grader_external_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    grader_role: Mapped[str] = mapped_column(String(50), nullable=False)
    points_awarded: Mapped[float] = mapped_column(Float, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    feedback: Mapped[str | None] = mapped_column(Text)
    grading_reason: Mapped[str | None] = mapped_column(Text)

    answer: Mapped["AssessmentAnswer"] = relationship(
        "AssessmentAnswer",
        foreign_keys=[assessment_answer_id],
        back_populates="manual_grades",
    )


class AssessmentReview(TimestampMixin, Base):
    """The current review state; every transition is preserved in the audit log."""

    __tablename__ = "assessment_reviews"
    __table_args__ = (
        UniqueConstraint(
            "assessment_attempt_id",
            name="uq_assessment_reviews_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reviewer_external_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AssessmentReviewStatus.PENDING.value,
    )
    review_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    attempt: Mapped["AssessmentAttempt"] = relationship(
        "AssessmentAttempt",
        back_populates="review",
    )


class GradingAuditEvent(CreatedAtMixin, Base):
    """An immutable record of a grading or review state transition."""

    __tablename__ = "grading_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assessment_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessment_answers.id", ondelete="RESTRICT"),
        index=True,
    )
    actor_external_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    previous_values_json: Mapped[
        dict[str, Any] | list[Any] | None
    ] = mapped_column(JSON)
    new_values_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )
    reason: Mapped[str | None] = mapped_column(Text)

    attempt: Mapped["AssessmentAttempt"] = relationship(
        "AssessmentAttempt",
        back_populates="grading_audit_events",
    )
    answer: Mapped["AssessmentAnswer | None"] = relationship(
        "AssessmentAnswer",
        foreign_keys=[assessment_answer_id],
    )


def _reject_immutable_change(
    mapper: object,
    connection: object,
    target: object,
) -> None:
    del mapper, connection, target
    raise ValueError("Grading history records are immutable")


for immutable_model in (ManualGrade, GradingAuditEvent):
    event.listen(immutable_model, "before_update", _reject_immutable_change)
    event.listen(immutable_model, "before_delete", _reject_immutable_change)


__all__ = [
    "AssessmentReview",
    "GradingAuditEvent",
    "ManualGrade",
]
