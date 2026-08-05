from __future__ import annotations

import json
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import (
    Assessment,
    Course,
    CourseEnrollment,
    Learner,
    Lesson,
    LessonProgress,
    Module,
)
from ..services.exceptions import ResourceNotFoundError
from ..services.learning import (
    add_lesson_time,
    create_assessment,
    create_learner,
    enroll_in_course,
    get_or_create_lesson_progress,
    start_lesson,
    update_lesson_progress,
)


LEARNER_EXTERNAL_ID = "nexora-example-learner"
LEARNER_EMAIL = "learner@example.nexora.local"
ASSESSMENT_SLUG = "market-basics-foundation-check"


def seed_learning(db: Session) -> dict[str, Any]:
    """Idempotently seed the Pack 2D Sprint 2 learner example."""
    course = db.scalar(select(Course).where(Course.slug == "market-basics"))
    if course is None:
        raise ResourceNotFoundError("Course", "market-basics")
    lessons = list(
        db.scalars(
            select(Lesson)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.course_id == course.id)
            .order_by(
                Module.display_order,
                Module.id,
                Lesson.display_order,
                Lesson.id,
            )
        )
    )
    if len(lessons) < 3:
        raise ResourceNotFoundError(
            "Market Basics seeded lessons",
            "expected at least three",
        )

    try:
        learner = db.scalar(
            select(Learner).where(
                or_(
                    Learner.external_user_id == LEARNER_EXTERNAL_ID,
                    Learner.email == LEARNER_EMAIL,
                )
            )
        )
        learner_created = learner is None
        if learner is None:
            learner = create_learner(
                db,
                {
                    "external_user_id": LEARNER_EXTERNAL_ID,
                    "email": LEARNER_EMAIL,
                    "display_name": "NEXORA Example Learner",
                },
                commit=False,
            )

        enrollment = db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.learner_id == learner.id,
                CourseEnrollment.course_id == course.id,
            )
        )
        enrollment_created = enrollment is None
        if enrollment is None:
            enrollment = enroll_in_course(
                db,
                learner.id,
                course.id,
                commit=False,
            )

        progress_created = 0
        for lesson in lessons[:3]:
            existing_progress = db.scalar(
                select(LessonProgress.id).where(
                    LessonProgress.learner_id == learner.id,
                    LessonProgress.lesson_id == lesson.id,
                )
            )
            if existing_progress is None:
                get_or_create_lesson_progress(
                    db,
                    learner.id,
                    lesson.id,
                    commit=False,
                )
                progress_created += 1

        first_progress = db.scalar(
            select(LessonProgress).where(
                LessonProgress.learner_id == learner.id,
                LessonProgress.lesson_id == lessons[0].id,
            )
        )
        if (
            first_progress is not None
            and first_progress.status == "not_started"
            and first_progress.progress_percent == 0
            and first_progress.time_spent_seconds == 0
        ):
            start_lesson(
                db,
                learner.id,
                lessons[0].id,
                commit=False,
            )
            add_lesson_time(
                db,
                learner.id,
                lessons[0].id,
                300,
                commit=False,
            )
            update_lesson_progress(
                db,
                learner.id,
                lessons[0].id,
                40.0,
                commit=False,
            )

        assessment = db.scalar(
            select(Assessment).where(Assessment.slug == ASSESSMENT_SLUG)
        )
        assessment_created = assessment is None
        if assessment is None:
            assessment = create_assessment(
                db,
                {
                    "lesson_id": lessons[0].id,
                    "title": "Market Basics Foundation Check",
                    "slug": ASSESSMENT_SLUG,
                    "description": (
                        "An example mixed-format assessment for the first "
                        "Market Basics lesson."
                    ),
                    "assessment_type": "quiz",
                    "passing_score": 70.0,
                    "max_attempts": 3,
                    "display_order": 0,
                    "questions": [
                        {
                            "question_type": "multiple_choice",
                            "prompt": (
                                "Which statement best describes a financial "
                                "market?"
                            ),
                            "points": 2.0,
                            "display_order": 0,
                            "options": [
                                {
                                    "option_text": (
                                        "A venue where financial claims are "
                                        "exchanged"
                                    ),
                                    "is_correct": True,
                                    "display_order": 0,
                                },
                                {
                                    "option_text": (
                                        "A guarantee that every investment "
                                        "earns a profit"
                                    ),
                                    "is_correct": False,
                                    "display_order": 1,
                                },
                                {
                                    "option_text": (
                                        "A system used only by central banks"
                                    ),
                                    "is_correct": False,
                                    "display_order": 2,
                                },
                            ],
                        },
                        {
                            "question_type": "true_false",
                            "prompt": (
                                "Financial markets can connect capital "
                                "providers with capital users."
                            ),
                            "points": 1.0,
                            "display_order": 1,
                            "options": [
                                {
                                    "option_text": "True",
                                    "is_correct": True,
                                    "display_order": 0,
                                },
                                {
                                    "option_text": "False",
                                    "is_correct": False,
                                    "display_order": 1,
                                },
                            ],
                        },
                        {
                            "question_type": "short_answer",
                            "prompt": (
                                "Name one function performed by a financial "
                                "market."
                            ),
                            "points": 2.0,
                            "display_order": 2,
                            "options": [],
                        },
                    ],
                },
                commit=False,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "learner_id": learner.id,
        "course_enrollment_id": enrollment.id,
        "lesson_progress_ids": [
            db.scalar(
                select(LessonProgress.id).where(
                    LessonProgress.learner_id == learner.id,
                    LessonProgress.lesson_id == lesson.id,
                )
            )
            for lesson in lessons[:3]
        ],
        "assessment_id": assessment.id,
        "learner_created": learner_created,
        "enrollment_created": enrollment_created,
        "progress_records_created": progress_created,
        "assessment_created": assessment_created,
    }


def main() -> None:
    with SessionLocal() as db:
        result = seed_learning(db)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
