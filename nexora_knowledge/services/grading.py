from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import exists, false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentQuestion,
    AssessmentReview,
    AssessmentReviewStatus,
    AttemptStatus,
    GradingAuditEvent,
    GradingAuditEventType,
    GradingStatus,
    Lesson,
    ManualGrade,
    Module,
    QuestionType,
)
from ..models.common import utc_now
from .authorization import (
    Principal,
    require_course_scope,
    require_grader,
    require_reviewer,
    require_review_requester,
    require_staff,
    scoped_course_ids,
)
from .exceptions import (
    AcademyInputError,
    ResourceConflictError,
    ResourceNotFoundError,
)


def _attempt_options():
    return (
        selectinload(AssessmentAttempt.answers).selectinload(
            AssessmentAnswer.question
        ),
        selectinload(AssessmentAttempt.answers).selectinload(
            AssessmentAnswer.current_manual_grade
        ),
        selectinload(AssessmentAttempt.assessment).selectinload(
            Assessment.questions
        ),
        selectinload(AssessmentAttempt.review),
    )


def _load_attempt(db: Session, attempt_id: int) -> AssessmentAttempt:
    attempt = db.scalar(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.id == attempt_id)
        .options(*_attempt_options())
        .execution_options(populate_existing=True)
    )
    if attempt is None:
        raise ResourceNotFoundError("AssessmentAttempt", attempt_id)
    return attempt


def _load_answer(db: Session, answer_id: int) -> AssessmentAnswer:
    answer = db.scalar(
        select(AssessmentAnswer)
        .where(AssessmentAnswer.id == answer_id)
        .options(
            selectinload(AssessmentAnswer.question),
            selectinload(AssessmentAnswer.current_manual_grade),
            selectinload(AssessmentAnswer.attempt)
            .selectinload(AssessmentAttempt.assessment)
            .selectinload(Assessment.questions),
            selectinload(AssessmentAnswer.attempt)
            .selectinload(AssessmentAttempt.answers)
            .selectinload(AssessmentAnswer.question),
            selectinload(AssessmentAnswer.attempt)
            .selectinload(AssessmentAttempt.answers)
            .selectinload(AssessmentAnswer.current_manual_grade),
        )
        .execution_options(populate_existing=True)
    )
    if answer is None:
        raise ResourceNotFoundError("AssessmentAnswer", answer_id)
    return answer


def _assessment_course_id(db: Session, assessment: Assessment) -> int | None:
    if assessment.course_id is not None:
        return assessment.course_id
    if assessment.module_id is not None:
        return db.scalar(
            select(Module.course_id).where(Module.id == assessment.module_id)
        )
    if assessment.lesson_id is not None:
        return db.scalar(
            select(Module.course_id)
            .join(Lesson, Lesson.module_id == Module.id)
            .where(Lesson.id == assessment.lesson_id)
        )
    return None


def _require_attempt_scope(
    db: Session,
    principal: Principal,
    attempt: AssessmentAttempt,
) -> None:
    require_course_scope(
        principal,
        _assessment_course_id(db, attempt.assessment),
    )


def _require_submitted(attempt: AssessmentAttempt) -> None:
    if attempt.status != AttemptStatus.SUBMITTED.value:
        raise ResourceConflictError(
            "Only submitted assessment attempts can be graded or reviewed"
        )


def _nonempty_reason(reason: str | None, *, required: bool) -> str | None:
    if reason is None:
        if required:
            raise AcademyInputError("An explicit reason is required")
        return None
    normalized = reason.strip()
    if not normalized:
        if required:
            raise AcademyInputError("An explicit reason is required")
        return None
    return normalized


def _grade_values(grade: ManualGrade | None) -> dict[str, Any] | None:
    if grade is None:
        return None
    return {
        "manual_grade_id": grade.id,
        "points_awarded": grade.points_awarded,
        "is_correct": grade.is_correct,
        "feedback": grade.feedback,
        "grading_reason": grade.grading_reason,
    }


def _attempt_values(attempt: AssessmentAttempt) -> dict[str, Any]:
    return {
        "grading_status": attempt.grading_status,
        "points_earned": attempt.points_earned,
        "score_percent": attempt.score_percent,
        "passed": attempt.passed,
        "final_score_percent": attempt.final_score_percent,
        "final_passed": attempt.final_passed,
    }


def _audit(
    db: Session,
    *,
    attempt_id: int,
    principal: Principal,
    event_type: GradingAuditEventType,
    answer_id: int | None = None,
    previous: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    reason: str | None = None,
) -> GradingAuditEvent:
    audit_event = GradingAuditEvent(
        assessment_attempt_id=attempt_id,
        assessment_answer_id=answer_id,
        actor_external_id=principal.external_id,
        actor_role=principal.role.value,
        event_type=event_type.value,
        previous_values_json=previous,
        new_values_json=new,
        reason=reason,
    )
    db.add(audit_event)
    db.flush()
    return audit_event


def _validate_manual_grade(
    answer: AssessmentAnswer,
    points_awarded: float,
) -> float:
    if answer.question.question_type != QuestionType.SHORT_ANSWER.value:
        raise AcademyInputError(
            "Manual grading is limited to short-answer questions"
        )
    points = float(points_awarded)
    if points < 0 or points > float(answer.question.points):
        raise AcademyInputError(
            "points_awarded must be between 0 and the question maximum "
            f"of {answer.question.points}"
        )
    return round(points, 4)


def _append_grade(
    db: Session,
    *,
    answer: AssessmentAnswer,
    principal: Principal,
    points_awarded: float,
    is_correct: bool | None,
    feedback: str | None,
    reason: str | None,
    require_existing: bool,
) -> ManualGrade:
    previous_grade = answer.current_manual_grade
    if require_existing and previous_grade is None:
        raise ResourceConflictError(
            "A grade must exist before it can be changed"
        )
    if not require_existing and previous_grade is not None:
        raise ResourceConflictError(
            "Answer is already graded; use the grade-change operation"
        )
    grade = ManualGrade(
        assessment_answer_id=answer.id,
        grader_external_id=principal.external_id,
        grader_role=principal.role.value,
        points_awarded=_validate_manual_grade(answer, points_awarded),
        is_correct=is_correct,
        feedback=feedback.strip() if feedback and feedback.strip() else None,
        grading_reason=reason,
    )
    db.add(grade)
    db.flush()
    answer.current_manual_grade_id = grade.id
    answer.current_manual_grade = grade
    answer.grading_status = GradingStatus.GRADED.value
    answer.graded_at = utc_now()
    db.flush()
    _audit(
        db,
        attempt_id=answer.attempt_id,
        answer_id=answer.id,
        principal=principal,
        event_type=(
            GradingAuditEventType.GRADE_CHANGED
            if previous_grade is not None
            else GradingAuditEventType.MANUAL_GRADE_CREATED
        ),
        previous=_grade_values(previous_grade),
        new=_grade_values(grade),
        reason=reason,
    )
    return grade


def recalculate_attempt(
    db: Session,
    attempt: AssessmentAttempt | int,
    principal: Principal,
) -> AssessmentAttempt:
    record = (
        _load_attempt(db, attempt)
        if isinstance(attempt, int)
        else _load_attempt(db, attempt.id)
    )
    _require_submitted(record)
    previous = _attempt_values(record)
    answers_by_question = {
        answer.question_id: answer for answer in record.answers
    }
    points_earned = 0.0
    fully_graded = len(answers_by_question) == len(
        record.assessment.questions
    )
    for question in record.assessment.questions:
        answer = answers_by_question.get(question.id)
        if answer is None:
            fully_graded = False
            continue
        if question.question_type == QuestionType.SHORT_ANSWER.value:
            if answer.current_manual_grade is None:
                fully_graded = False
                continue
            points_earned += answer.current_manual_grade.points_awarded
        else:
            if answer.points_awarded is None:
                fully_graded = False
                continue
            points_earned += answer.points_awarded
    points_possible = sum(
        float(question.points) for question in record.assessment.questions
    )
    score = round(
        points_earned * 100.0 / points_possible
        if points_possible > 0
        else 0.0,
        2,
    )
    record.points_earned = round(points_earned, 4)
    record.points_possible = round(points_possible, 4)
    record.score_percent = score
    if fully_graded:
        passed = score >= record.assessment.passing_score
        record.passed = passed
        record.final_score_percent = score
        record.final_passed = passed
        record.grading_status = GradingStatus.GRADED.value
    else:
        record.passed = None
        record.final_score_percent = None
        record.final_passed = None
        record.grading_status = GradingStatus.MANUAL_GRADING_REQUIRED.value
    db.flush()
    _audit(
        db,
        attempt_id=record.id,
        principal=principal,
        event_type=GradingAuditEventType.ATTEMPT_RECALCULATED,
        previous=previous,
        new=_attempt_values(record),
    )
    return record


def grade_short_answer(
    db: Session,
    answer_id: int,
    *,
    principal: Principal,
    points_awarded: float,
    is_correct: bool | None = None,
    feedback: str | None = None,
    grading_reason: str | None = None,
    commit: bool = True,
) -> ManualGrade:
    require_grader(principal)
    answer = _load_answer(db, answer_id)
    _require_submitted(answer.attempt)
    _require_attempt_scope(db, principal, answer.attempt)
    reason = _nonempty_reason(grading_reason, required=False)
    try:
        grade = _append_grade(
            db,
            answer=answer,
            principal=principal,
            points_awarded=points_awarded,
            is_correct=is_correct,
            feedback=feedback,
            reason=reason,
            require_existing=False,
        )
        recalculate_attempt(db, answer.attempt_id, principal)
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(grade)
        return grade
    except Exception:
        db.rollback()
        raise


def change_grade(
    db: Session,
    answer_id: int,
    *,
    principal: Principal,
    points_awarded: float,
    grading_reason: str,
    is_correct: bool | None = None,
    feedback: str | None = None,
    commit: bool = True,
) -> ManualGrade:
    require_grader(principal)
    answer = _load_answer(db, answer_id)
    _require_submitted(answer.attempt)
    _require_attempt_scope(db, principal, answer.attempt)
    reason = _nonempty_reason(grading_reason, required=True)
    try:
        grade = _append_grade(
            db,
            answer=answer,
            principal=principal,
            points_awarded=points_awarded,
            is_correct=is_correct,
            feedback=feedback,
            reason=reason,
            require_existing=True,
        )
        recalculate_attempt(db, answer.attempt_id, principal)
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(grade)
        return grade
    except Exception:
        db.rollback()
        raise


def list_manual_grades(
    db: Session,
    answer_id: int,
    *,
    principal: Principal,
) -> list[ManualGrade]:
    require_staff(principal)
    answer = _load_answer(db, answer_id)
    _require_attempt_scope(db, principal, answer.attempt)
    return list(
        db.scalars(
            select(ManualGrade)
            .where(ManualGrade.assessment_answer_id == answer_id)
            .order_by(ManualGrade.created_at, ManualGrade.id)
        )
    )


def list_audit_events(
    db: Session,
    *,
    principal: Principal,
    attempt_id: int | None = None,
    answer_id: int | None = None,
    event_type: str | None = None,
    actor_external_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[GradingAuditEvent]:
    require_staff(principal)
    statement = _audit_events_statement(
        db,
        principal=principal,
        attempt_id=attempt_id,
        answer_id=answer_id,
        event_type=event_type,
        actor_external_id=actor_external_id,
        date_from=date_from,
        date_to=date_to,
    )
    return list(
        db.scalars(
            statement.order_by(
                GradingAuditEvent.created_at.desc(),
                GradingAuditEvent.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )


def _audit_events_statement(
    db: Session,
    *,
    principal: Principal,
    attempt_id: int | None,
    answer_id: int | None,
    event_type: str | None,
    actor_external_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    statement = select(GradingAuditEvent)
    if attempt_id is not None:
        attempt = _load_attempt(db, attempt_id)
        _require_attempt_scope(db, principal, attempt)
        statement = statement.where(
            GradingAuditEvent.assessment_attempt_id == attempt_id
        )
    if answer_id is not None:
        answer = _load_answer(db, answer_id)
        _require_attempt_scope(db, principal, answer.attempt)
        statement = statement.where(
            GradingAuditEvent.assessment_answer_id == answer_id
        )
    if event_type is not None:
        statement = statement.where(
            GradingAuditEvent.event_type == event_type
        )
    if actor_external_id is not None:
        statement = statement.where(
            GradingAuditEvent.actor_external_id == actor_external_id
        )
    if date_from is not None:
        statement = statement.where(
            GradingAuditEvent.created_at >= date_from
        )
    if date_to is not None:
        statement = statement.where(
            GradingAuditEvent.created_at <= date_to
        )
    return statement


def count_audit_events(
    db: Session,
    *,
    principal: Principal,
    attempt_id: int | None = None,
    answer_id: int | None = None,
    event_type: str | None = None,
    actor_external_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    require_staff(principal)
    statement = _audit_events_statement(
        db,
        principal=principal,
        attempt_id=attempt_id,
        answer_id=answer_id,
        event_type=event_type,
        actor_external_id=actor_external_id,
        date_from=date_from,
        date_to=date_to,
    )
    return int(
        db.scalar(
            select(func.count()).select_from(
                statement.order_by(None).subquery()
            )
        )
        or 0
    )


def list_attempts_needing_grading(
    db: Session,
    *,
    principal: Principal,
    assessment_id: int | None = None,
    learner_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AssessmentAttempt]:
    require_staff(principal)
    statement = _attempts_needing_grading_statement(
        principal=principal,
        assessment_id=assessment_id,
        learner_id=learner_id,
    ).options(selectinload(AssessmentAttempt.assessment))
    return list(
        db.scalars(
            statement.order_by(
                AssessmentAttempt.submitted_at,
                AssessmentAttempt.id,
            )
            .offset(offset)
            .limit(limit)
        )
    )


def _attempts_needing_grading_statement(
    *,
    principal: Principal,
    assessment_id: int | None,
    learner_id: int | None,
):
    needs_manual_grade = exists(
        select(AssessmentAnswer.id)
        .join(
            AssessmentQuestion,
            AssessmentQuestion.id == AssessmentAnswer.question_id,
        )
        .where(
            AssessmentAnswer.attempt_id == AssessmentAttempt.id,
            AssessmentQuestion.question_type
            == QuestionType.SHORT_ANSWER.value,
            AssessmentAnswer.current_manual_grade_id.is_(None),
        )
    )
    statement = (
        select(AssessmentAttempt)
        .where(
            AssessmentAttempt.status == AttemptStatus.SUBMITTED.value,
            needs_manual_grade,
        )
    )
    if assessment_id is not None:
        statement = statement.where(
            AssessmentAttempt.assessment_id == assessment_id
        )
    if learner_id is not None:
        statement = statement.where(
            AssessmentAttempt.learner_id == learner_id
        )
    course_ids = scoped_course_ids(principal)
    if course_ids is not None:
        if not course_ids:
            statement = statement.where(false())
        else:
            eligible_assessment_ids = select(Assessment.id).where(
                or_(
                    Assessment.course_id.in_(course_ids),
                    Assessment.module_id.in_(
                        select(Module.id).where(
                            Module.course_id.in_(course_ids)
                        )
                    ),
                    Assessment.lesson_id.in_(
                        select(Lesson.id)
                        .join(Module, Module.id == Lesson.module_id)
                        .where(Module.course_id.in_(course_ids))
                    ),
                )
            )
            statement = statement.where(
                AssessmentAttempt.assessment_id.in_(
                    eligible_assessment_ids
                )
            )
    return statement


def count_attempts_needing_grading(
    db: Session,
    *,
    principal: Principal,
    assessment_id: int | None = None,
    learner_id: int | None = None,
) -> int:
    require_staff(principal)
    statement = _attempts_needing_grading_statement(
        principal=principal,
        assessment_id=assessment_id,
        learner_id=learner_id,
    )
    return int(
        db.scalar(
            select(func.count()).select_from(
                statement.order_by(None).subquery()
            )
        )
        or 0
    )


def get_attempt_for_staff(
    db: Session,
    attempt_id: int,
    *,
    principal: Principal,
) -> AssessmentAttempt:
    require_staff(principal)
    attempt = _load_attempt(db, attempt_id)
    _require_attempt_scope(db, principal, attempt)
    return attempt


def _set_review(
    db: Session,
    *,
    attempt: AssessmentAttempt,
    principal: Principal,
    status: AssessmentReviewStatus,
    reason: str | None,
    notes: str | None,
    event_type: GradingAuditEventType,
    record_audit: bool = True,
) -> AssessmentReview:
    review = attempt.review
    previous = (
        {
            "review_status": review.review_status,
            "review_reason": review.review_reason,
            "notes": review.notes,
        }
        if review is not None
        else None
    )
    if review is None:
        review = AssessmentReview(assessment_attempt_id=attempt.id)
        db.add(review)
        attempt.review = review
    review.reviewer_external_id = principal.external_id
    review.review_status = status.value
    review.review_reason = reason
    review.notes = notes.strip() if notes and notes.strip() else None
    db.flush()
    if record_audit:
        _audit(
            db,
            attempt_id=attempt.id,
            principal=principal,
            event_type=event_type,
            previous=previous,
            new={
                "review_status": review.review_status,
                "review_reason": review.review_reason,
                "notes": review.notes,
            },
            reason=reason,
        )
    return review


def request_review(
    db: Session,
    attempt_id: int,
    *,
    principal: Principal,
    reason: str | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> AssessmentReview:
    require_review_requester(principal)
    attempt = _load_attempt(db, attempt_id)
    _require_attempt_scope(db, principal, attempt)
    _require_submitted(attempt)
    if (
        attempt.review is not None
        and attempt.review.review_status
        == AssessmentReviewStatus.PENDING.value
    ):
        raise ResourceConflictError("Attempt review is already pending")
    normalized_reason = _nonempty_reason(reason, required=False)
    try:
        review = _set_review(
            db,
            attempt=attempt,
            principal=principal,
            status=AssessmentReviewStatus.PENDING,
            reason=normalized_reason,
            notes=notes,
            event_type=GradingAuditEventType.REVIEW_REQUESTED,
        )
        attempt.grading_status = GradingStatus.REVIEW_PENDING.value
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(review)
        return review
    except Exception:
        db.rollback()
        raise


def approve_review(
    db: Session,
    attempt_id: int,
    *,
    principal: Principal,
    reason: str,
    notes: str | None = None,
    commit: bool = True,
) -> AssessmentReview:
    require_reviewer(principal)
    attempt = _load_attempt(db, attempt_id)
    _require_attempt_scope(db, principal, attempt)
    _require_submitted(attempt)
    if (
        attempt.review is None
        or attempt.review.review_status
        != AssessmentReviewStatus.PENDING.value
    ):
        raise ResourceConflictError("Only a pending review can be approved")
    if attempt.final_score_percent is None:
        raise ResourceConflictError(
            "An attempt cannot be approved until grading is complete"
        )
    normalized_reason = _nonempty_reason(reason, required=True)
    try:
        review = _set_review(
            db,
            attempt=attempt,
            principal=principal,
            status=AssessmentReviewStatus.APPROVED,
            reason=normalized_reason,
            notes=notes,
            event_type=GradingAuditEventType.REVIEW_APPROVED,
        )
        attempt.grading_status = GradingStatus.FINAL.value
        attempt.reviewed_at = utc_now()
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(review)
        return review
    except Exception:
        db.rollback()
        raise


def request_grading_changes(
    db: Session,
    attempt_id: int,
    *,
    principal: Principal,
    reason: str,
    notes: str | None = None,
    commit: bool = True,
) -> AssessmentReview:
    require_reviewer(principal)
    attempt = _load_attempt(db, attempt_id)
    _require_attempt_scope(db, principal, attempt)
    _require_submitted(attempt)
    if (
        attempt.review is None
        or attempt.review.review_status
        != AssessmentReviewStatus.PENDING.value
    ):
        raise ResourceConflictError(
            "Changes can only be requested from a pending review"
        )
    normalized_reason = _nonempty_reason(reason, required=True)
    try:
        review = _set_review(
            db,
            attempt=attempt,
            principal=principal,
            status=AssessmentReviewStatus.CHANGES_REQUESTED,
            reason=normalized_reason,
            notes=notes,
            event_type=GradingAuditEventType.REVIEW_CHANGES_REQUESTED,
        )
        attempt.grading_status = GradingStatus.CHANGES_REQUESTED.value
        attempt.reviewed_at = utc_now()
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(review)
        return review
    except Exception:
        db.rollback()
        raise


def regrade_attempt(
    db: Session,
    attempt_id: int,
    grades: Sequence[Mapping[str, Any] | Any],
    *,
    principal: Principal,
    reason: str,
    notes: str | None = None,
    commit: bool = True,
) -> AssessmentAttempt:
    require_reviewer(principal)
    attempt = _load_attempt(db, attempt_id)
    _require_attempt_scope(db, principal, attempt)
    _require_submitted(attempt)
    normalized_reason = _nonempty_reason(reason, required=True)
    grade_values = [
        (
            item.model_dump()
            if hasattr(item, "model_dump")
            else dict(item)
        )
        for item in grades
    ]
    answer_ids = [int(item["assessment_answer_id"]) for item in grade_values]
    if len(answer_ids) != len(set(answer_ids)):
        raise AcademyInputError("Regrade payload contains duplicate answers")
    short_answers = {
        answer.id: answer
        for answer in attempt.answers
        if answer.question.question_type == QuestionType.SHORT_ANSWER.value
    }
    if set(answer_ids) != set(short_answers):
        raise AcademyInputError(
            "A full regrade must include every short-answer response"
        )
    previous_attempt = _attempt_values(attempt)
    try:
        for item in grade_values:
            answer = short_answers[int(item["assessment_answer_id"])]
            _append_grade(
                db,
                answer=answer,
                principal=principal,
                points_awarded=float(item["points_awarded"]),
                is_correct=item.get("is_correct"),
                feedback=item.get("feedback"),
                reason=normalized_reason,
                require_existing=answer.current_manual_grade is not None,
            )
        recalculate_attempt(db, attempt.id, principal)
        attempt = _load_attempt(db, attempt.id)
        attempt.grading_status = GradingStatus.REGRADED.value
        attempt.reviewed_at = utc_now()
        _set_review(
            db,
            attempt=attempt,
            principal=principal,
            status=AssessmentReviewStatus.REGRADED,
            reason=normalized_reason,
            notes=notes,
            event_type=GradingAuditEventType.ATTEMPT_REGRADED,
            record_audit=False,
        )
        _audit(
            db,
            attempt_id=attempt.id,
            principal=principal,
            event_type=GradingAuditEventType.ATTEMPT_REGRADED,
            previous=previous_attempt,
            new={
                **_attempt_values(attempt),
                "review_status": AssessmentReviewStatus.REGRADED.value,
            },
            reason=normalized_reason,
        )
        if commit:
            db.commit()
        else:
            db.flush()
        return _load_attempt(db, attempt.id)
    except Exception:
        db.rollback()
        raise


__all__ = [
    "approve_review",
    "change_grade",
    "count_audit_events",
    "count_attempts_needing_grading",
    "grade_short_answer",
    "get_attempt_for_staff",
    "list_attempts_needing_grading",
    "list_audit_events",
    "list_manual_grades",
    "recalculate_attempt",
    "regrade_attempt",
    "request_grading_changes",
    "request_review",
]
