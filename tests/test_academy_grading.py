from __future__ import annotations

import pytest
from sqlalchemy import select

from nexora_knowledge.models import (
    GradingAuditEvent,
    ManualGrade,
)
from nexora_knowledge.services.authorization import Principal
from nexora_knowledge.services.curriculum import (
    create_course,
    create_degree,
    create_lesson,
    create_module,
    create_school,
)
from nexora_knowledge.services.exceptions import (
    AcademyInputError,
    AuthorizationDeniedError,
    ResourceConflictError,
)
from nexora_knowledge.services.grading import (
    approve_review,
    change_grade,
    grade_short_answer,
    list_audit_events,
    list_manual_grades,
    regrade_attempt,
    request_grading_changes,
    request_review,
)
from nexora_knowledge.services.learning import (
    create_assessment,
    create_learner,
    start_assessment_attempt,
    submit_assessment_attempt,
)


def mixed_attempt(db, suffix: str = "one"):
    school = create_school(
        db,
        {
            "name": f"School {suffix}",
            "slug": f"school-{suffix}",
        },
    )
    degree = create_degree(
        db,
        {
            "school_id": school.id,
            "name": f"Degree {suffix}",
            "slug": f"degree-{suffix}",
            "level": "foundation",
        },
    )
    course = create_course(
        db,
        {
            "degree_id": degree.id,
            "name": f"Course {suffix}",
            "slug": f"course-{suffix}",
        },
    )
    module = create_module(
        db,
        {
            "course_id": course.id,
            "name": f"Module {suffix}",
            "slug": f"module-{suffix}",
        },
    )
    lesson = create_lesson(
        db,
        {
            "module_id": module.id,
            "title": f"Lesson {suffix}",
            "slug": f"lesson-{suffix}",
            "status": "published",
        },
    )
    learner = create_learner(
        db,
        {
            "external_user_id": f"learner-{suffix}",
            "email": f"{suffix}@example.com",
            "display_name": f"Learner {suffix}",
        },
    )
    assessment = create_assessment(
        db,
        {
            "lesson_id": lesson.id,
            "title": f"Assessment {suffix}",
            "slug": f"assessment-{suffix}",
            "passing_score": 70,
            "questions": [
                {
                    "question_type": "multiple_choice",
                    "prompt": "Choose A",
                    "points": 2,
                    "options": [
                        {"option_text": "A", "is_correct": True},
                        {"option_text": "B", "is_correct": False},
                    ],
                },
                {
                    "question_type": "short_answer",
                    "prompt": "Explain the choice",
                    "points": 3,
                    "options": [],
                },
            ],
        },
    )
    attempt = start_assessment_attempt(db, learner.id, assessment.id)
    attempt = submit_assessment_attempt(
        db,
        attempt.id,
        [
            {
                "question_id": assessment.questions[0].id,
                "selected_option_id": assessment.questions[0].options[0].id,
            },
            {
                "question_id": assessment.questions[1].id,
                "text_answer": "Because it is the supported answer.",
            },
        ],
    )
    short_answer = next(
        item
        for item in attempt.answers
        if item.question_id == assessment.questions[1].id
    )
    return course, learner, assessment, attempt, short_answer


def test_manual_grade_recalculation_and_append_only_change(db) -> None:
    _, _, _, attempt, answer = mixed_attempt(db)
    instructor = Principal("instructor-1", "instructor")

    first = grade_short_answer(
        db,
        answer.id,
        principal=instructor,
        points_awarded=3,
        is_correct=True,
        feedback="Complete explanation",
    )
    db.refresh(attempt)
    assert attempt.automatic_points_earned == 2
    assert attempt.automatic_score_percent == 40
    assert attempt.score_percent == 100
    assert attempt.final_score_percent == 100
    assert attempt.final_passed is True

    changed = change_grade(
        db,
        answer.id,
        principal=instructor,
        points_awarded=1,
        is_correct=False,
        feedback="Missed the risk constraint",
        grading_reason="Rubric correction",
    )
    db.refresh(attempt)
    assert first.id != changed.id
    assert first.points_awarded == 3
    assert changed.points_awarded == 1
    assert attempt.final_score_percent == 60
    assert attempt.final_passed is False
    assert [item.id for item in list_manual_grades(
        db, answer.id, principal=instructor
    )] == [first.id, changed.id]


def test_manual_grade_validation_and_role_boundary(db) -> None:
    _, _, _, _, answer = mixed_attempt(db)
    with pytest.raises(AuthorizationDeniedError):
        grade_short_answer(
            db,
            answer.id,
            principal=Principal("learner-one", "learner"),
            points_awarded=2,
        )
    with pytest.raises(AcademyInputError):
        grade_short_answer(
            db,
            answer.id,
            principal=Principal("instructor-1", "instructor"),
            points_awarded=3.01,
        )


def test_grade_change_requires_reason_and_prior_grade(db) -> None:
    _, _, _, _, answer = mixed_attempt(db)
    instructor = Principal("instructor-1", "instructor")
    with pytest.raises(AcademyInputError):
        change_grade(
            db,
            answer.id,
            principal=instructor,
            points_awarded=1,
            grading_reason=" ",
        )
    with pytest.raises(ResourceConflictError):
        change_grade(
            db,
            answer.id,
            principal=instructor,
            points_awarded=1,
            grading_reason="New rubric",
        )


def test_review_transitions_and_regrade(db) -> None:
    _, _, _, attempt, answer = mixed_attempt(db)
    instructor = Principal("instructor-1", "instructor")
    reviewer = Principal("reviewer-1", "reviewer")
    grade_short_answer(
        db,
        answer.id,
        principal=instructor,
        points_awarded=3,
    )
    review = request_review(
        db,
        attempt.id,
        principal=instructor,
        reason="Second check requested",
    )
    assert review.review_status == "pending"
    with pytest.raises(ResourceConflictError):
        request_review(db, attempt.id, principal=instructor)

    changes = request_grading_changes(
        db,
        attempt.id,
        principal=reviewer,
        reason="Apply the revised rubric",
    )
    assert changes.review_status == "changes_requested"
    regraded = regrade_attempt(
        db,
        attempt.id,
        [
            {
                "assessment_answer_id": answer.id,
                "points_awarded": 2,
                "is_correct": True,
            }
        ],
        principal=reviewer,
        reason="Revised rubric applied",
    )
    assert regraded.grading_status == "regraded"
    assert regraded.final_score_percent == 80
    assert regraded.review.review_status == "regraded"


def test_review_approval_and_invalid_transition(db) -> None:
    _, _, _, attempt, answer = mixed_attempt(db)
    instructor = Principal("instructor-1", "instructor")
    reviewer = Principal("reviewer-1", "reviewer")
    grade_short_answer(
        db, answer.id, principal=instructor, points_awarded=3
    )
    request_review(db, attempt.id, principal=instructor)
    approved = approve_review(
        db,
        attempt.id,
        principal=reviewer,
        reason="Grade and feedback verified",
    )
    assert approved.review_status == "approved"
    db.refresh(attempt)
    assert attempt.grading_status == "final"
    assert attempt.reviewed_at is not None
    with pytest.raises(ResourceConflictError):
        approve_review(
            db,
            attempt.id,
            principal=reviewer,
            reason="Duplicate approval",
        )


def test_grading_and_audit_rows_are_immutable(db) -> None:
    _, _, _, attempt, answer = mixed_attempt(db)
    instructor = Principal("instructor-1", "instructor")
    grade = grade_short_answer(
        db, answer.id, principal=instructor, points_awarded=2
    )
    events = list_audit_events(
        db, principal=instructor, attempt_id=attempt.id
    )
    assert {item.event_type for item in events} >= {
        "manual_grade_created",
        "attempt_recalculated",
    }

    grade.points_awarded = 0
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()

    audit_event = db.scalar(
        select(GradingAuditEvent).where(
            GradingAuditEvent.id == events[0].id
        )
    )
    audit_event.reason = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()
    assert db.scalar(
        select(ManualGrade.points_awarded).where(ManualGrade.id == grade.id)
    ) == 2
