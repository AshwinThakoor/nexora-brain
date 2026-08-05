from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from nexora_knowledge.models.enums import (
    DifficultyLevel,
    KnowledgeLifecycleStatus,
)
from nexora_knowledge.schemas.curriculum import (
    CourseCreate,
    CurriculumPathCreate,
    CurriculumPathLessonCreate,
    DegreeCreate,
    LearningObjectiveCreate,
    LessonCreate,
    LessonPrerequisiteCreate,
    LessonRead,
    LessonUpdate,
    ModuleCreate,
    SchoolCreate,
    SchoolUpdate,
)


def test_curriculum_create_schemas_cover_every_entity() -> None:
    assert SchoolCreate(name="Markets", slug="markets").display_order == 0
    assert (
        DegreeCreate(
            school_id=1,
            name="Foundation",
            slug="foundation",
            level="foundation",
        ).estimated_hours
        == 0
    )
    assert (
        CourseCreate(
            degree_id=1,
            name="Basics",
            slug="basics",
        ).display_order
        == 0
    )
    assert (
        ModuleCreate(
            course_id=1,
            name="Introduction",
            slug="introduction",
        ).estimated_minutes
        == 0
    )
    lesson = LessonCreate(
        module_id=1,
        title="Liquidity",
        slug="liquidity",
    )
    assert lesson.difficulty_level is DifficultyLevel.BEGINNER
    assert lesson.status is KnowledgeLifecycleStatus.DRAFT
    assert LearningObjectiveCreate(
        lesson_id=1,
        objective="Define liquidity.",
    ).display_order == 0
    assert LessonPrerequisiteCreate(
        lesson_id=2,
        prerequisite_lesson_id=1,
    ).prerequisite_lesson_id == 1
    assert CurriculumPathCreate(
        name="Foundation Path",
        slug="foundation-path",
    ).name == "Foundation Path"
    assert CurriculumPathLessonCreate(
        curriculum_path_id=1,
        lesson_id=1,
        display_order=0,
    ).display_order == 0


def test_curriculum_schema_validation_and_partial_updates() -> None:
    with pytest.raises(ValidationError):
        SchoolCreate(name="Markets", slug="Not Normalized")
    with pytest.raises(ValidationError):
        LessonCreate(
            module_id=1,
            title="Liquidity",
            slug="liquidity",
            estimated_minutes=-1,
        )
    with pytest.raises(ValidationError):
        LessonCreate(
            module_id=1,
            title="Liquidity",
            slug="liquidity",
            difficulty_level="unreviewed",
        )
    with pytest.raises(ValidationError):
        SchoolUpdate(name=None)
    with pytest.raises(ValidationError):
        LessonUpdate(status=None)

    update = SchoolUpdate(description=None, icon=None)
    assert update.model_fields_set == {"description", "icon"}


def test_lesson_read_schema_accepts_orm_shaped_data() -> None:
    timestamp = datetime.now(timezone.utc)
    lesson = LessonRead.model_validate(
        {
            "id": 1,
            "module_id": 1,
            "knowledge_article_id": None,
            "concept_id": None,
            "title": "Liquidity",
            "slug": "liquidity",
            "summary": None,
            "estimated_minutes": 20,
            "difficulty_level": "beginner",
            "status": "draft",
            "display_order": 0,
            "created_at": timestamp,
            "updated_at": timestamp,
            "objectives": [
                {
                    "id": 1,
                    "lesson_id": 1,
                    "objective": "Define liquidity.",
                    "display_order": 0,
                }
            ],
            "prerequisite_links": [],
        }
    )
    assert lesson.objectives[0].objective == "Define liquidity."

