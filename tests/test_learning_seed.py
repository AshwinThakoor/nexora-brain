from __future__ import annotations

from sqlalchemy import func, select

from nexora_knowledge.models import (
    Assessment,
    AssessmentQuestion,
    CourseEnrollment,
    Learner,
    LessonProgress,
)
from nexora_knowledge.seeds.academy_seed import seed_academy
from nexora_knowledge.seeds.learning_seed import seed_learning


def test_learning_seed_is_idempotent_and_links_seeded_curriculum(db) -> None:
    academy = seed_academy(db)
    first = seed_learning(db)
    second = seed_learning(db)

    assert first["learner_id"] == second["learner_id"]
    assert first["assessment_id"] == second["assessment_id"]
    assert first["course_enrollment_id"] == second["course_enrollment_id"]
    assert second["learner_created"] is False
    assert second["enrollment_created"] is False
    assert second["assessment_created"] is False
    assert second["progress_records_created"] == 0
    assert db.scalar(select(func.count()).select_from(Learner)) == 1
    assert (
        db.scalar(select(func.count()).select_from(CourseEnrollment)) == 1
    )
    assert db.scalar(select(func.count()).select_from(LessonProgress)) == 3
    assert db.scalar(select(func.count()).select_from(Assessment)) == 1
    assert (
        db.scalar(select(func.count()).select_from(AssessmentQuestion)) == 3
    )

    enrollment = db.get(CourseEnrollment, first["course_enrollment_id"])
    assessment = db.get(Assessment, first["assessment_id"])
    assert enrollment.course_id == academy["course_id"]
    assert assessment.lesson_id == academy["lesson_ids"][0]
    assert enrollment.status != "completed"
