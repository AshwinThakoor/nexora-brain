from __future__ import annotations

import pytest
from sqlalchemy import func, select

from nexora_knowledge.models import (
    Course,
    CurriculumPath,
    CurriculumPathLesson,
    Degree,
    LearningObjective,
    Lesson,
    LessonPrerequisite,
    Module,
    School,
)
from nexora_knowledge.services.curriculum import (
    add_lesson_to_curriculum_path,
    create_course,
    create_curriculum_path,
    create_degree,
    create_learning_objective,
    create_lesson,
    create_lesson_prerequisite,
    create_module,
    create_school,
    delete_school,
    get_curriculum_path,
    get_curriculum_path_by_slug,
    get_school,
    list_curriculum_path_lessons,
    list_learning_objectives,
    list_lessons,
    remove_lesson_from_curriculum_path,
    replace_curriculum_path_lessons,
    update_course,
    update_curriculum_path,
    update_curriculum_path_lesson,
    update_degree,
    update_learning_objective,
    update_lesson,
    update_lesson_prerequisite,
    update_module,
    update_school,
)
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def create_hierarchy(db):
    school = create_school(
        db,
        {
            "name": "Financial Markets",
            "slug": "financial-markets",
            "display_order": 0,
        },
    )
    degree = create_degree(
        db,
        {
            "school_id": school.id,
            "name": "Foundation",
            "slug": "foundation",
            "level": "foundation",
            "estimated_hours": 1,
        },
    )
    course = create_course(
        db,
        {
            "degree_id": degree.id,
            "name": "Market Basics",
            "slug": "market-basics",
            "estimated_hours": 1,
        },
    )
    module = create_module(
        db,
        {
            "course_id": course.id,
            "name": "Introduction",
            "slug": "introduction",
            "estimated_minutes": 60,
        },
    )
    return school, degree, course, module


def create_three_lessons(db, module_id: int):
    return [
        create_lesson(
            db,
            {
                "module_id": module_id,
                "title": title,
                "slug": slug,
                "display_order": display_order,
                "estimated_minutes": 10,
            },
        )
        for title, slug, display_order in (
            ("Liquidity", "liquidity", 2),
            ("Markets", "markets", 0),
            ("Supply and Demand", "supply-and-demand", 1),
        )
    ]


def test_curriculum_crud_hierarchy_and_unique_slugs(db) -> None:
    school, degree, course, module = create_hierarchy(db)

    with pytest.raises(ResourceConflictError):
        create_school(
            db,
            {"name": "Duplicate", "slug": "financial-markets"},
        )
    with pytest.raises(ResourceNotFoundError):
        create_degree(
            db,
            {
                "school_id": 9999,
                "name": "Missing Parent",
                "slug": "missing-parent",
                "level": "foundation",
            },
        )

    update_school(db, school.id, {"name": "Global Markets"})
    update_degree(db, degree.id, {"estimated_hours": 2.5})
    update_course(db, course.id, {"name": "Market Essentials"})
    update_module(db, module.id, {"estimated_minutes": 75})
    refreshed = get_school(db, school.id)
    assert refreshed.name == "Global Markets"
    assert refreshed.degrees[0].estimated_hours == 2.5
    assert refreshed.degrees[0].courses[0].name == "Market Essentials"
    assert (
        refreshed.degrees[0].courses[0].modules[0].estimated_minutes
        == 75
    )


def test_ordered_lessons_objectives_and_curriculum_path(db) -> None:
    _, _, _, module = create_hierarchy(db)
    liquidity, markets, supply = create_three_lessons(db, module.id)

    assert [
        lesson.title for lesson in list_lessons(db, module_id=module.id)
    ] == ["Markets", "Supply and Demand", "Liquidity"]

    first = create_learning_objective(
        db,
        {
            "lesson_id": markets.id,
            "objective": "Second objective",
            "display_order": 1,
        },
    )
    create_learning_objective(
        db,
        {
            "lesson_id": markets.id,
            "objective": "First objective",
            "display_order": 0,
        },
    )
    update_learning_objective(db, first.id, {"objective": "Updated second"})
    assert [
        item.objective
        for item in list_learning_objectives(db, lesson_id=markets.id)
    ] == ["First objective", "Updated second"]

    path = create_curriculum_path(
        db,
        {
            "name": "Foundation Path",
            "slug": "foundation-path",
            "lesson_ids": [markets.id, supply.id],
        },
    )
    add_lesson_to_curriculum_path(db, path.id, liquidity.id)
    assert [
        link.lesson_id for link in list_curriculum_path_lessons(db, path.id)
    ] == [markets.id, supply.id, liquidity.id]

    update_curriculum_path_lesson(
        db,
        path.id,
        liquidity.id,
        {"display_order": 3},
    )
    remove_lesson_from_curriculum_path(db, path.id, supply.id)
    replace_curriculum_path_lessons(
        db,
        path.id,
        [liquidity.id, markets.id],
    )
    assert [
        lesson.id for lesson in get_curriculum_path(db, path.id).lessons
    ] == [liquidity.id, markets.id]

    update_lesson(db, liquidity.id, {"summary": "Updated summary"})
    assert liquidity.summary == "Updated summary"


def test_prerequisite_validation_prevents_duplicates_self_and_cycles(db) -> None:
    _, _, _, module = create_hierarchy(db)
    liquidity, markets, supply = create_three_lessons(db, module.id)

    markets_requires_liquidity = create_lesson_prerequisite(
        db,
        {
            "lesson_id": markets.id,
            "prerequisite_lesson_id": liquidity.id,
        },
    )
    create_lesson_prerequisite(
        db,
        {
            "lesson_id": supply.id,
            "prerequisite_lesson_id": markets.id,
        },
    )
    with pytest.raises(ResourceConflictError):
        create_lesson_prerequisite(
            db,
            {
                "lesson_id": markets.id,
                "prerequisite_lesson_id": liquidity.id,
            },
        )
    with pytest.raises(ResourceValidationError):
        create_lesson_prerequisite(
            db,
            {
                "lesson_id": markets.id,
                "prerequisite_lesson_id": markets.id,
            },
        )
    with pytest.raises(ResourceValidationError):
        create_lesson_prerequisite(
            db,
            {
                "lesson_id": liquidity.id,
                "prerequisite_lesson_id": supply.id,
            },
        )

    update_lesson_prerequisite(
        db,
        markets_requires_liquidity.id,
        {"lesson_id": supply.id, "prerequisite_lesson_id": liquidity.id},
    )
    assert markets_requires_liquidity.lesson_id == supply.id


def test_school_delete_cascades_hierarchy_and_lesson_dependents(db) -> None:
    school, _, _, module = create_hierarchy(db)
    liquidity, markets, supply = create_three_lessons(db, module.id)
    create_learning_objective(
        db,
        {
            "lesson_id": markets.id,
            "objective": "Understand markets.",
        },
    )
    create_lesson_prerequisite(
        db,
        {
            "lesson_id": supply.id,
            "prerequisite_lesson_id": markets.id,
        },
    )
    path = create_curriculum_path(
        db,
        {
            "name": "Foundation Path",
            "slug": "foundation-path",
            "lesson_ids": [markets.id, supply.id, liquidity.id],
        },
    )

    delete_school(db, school.id)

    for model in (
        School,
        Degree,
        Course,
        Module,
        Lesson,
        LearningObjective,
        LessonPrerequisite,
        CurriculumPathLesson,
    ):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert db.get(CurriculumPath, path.id) is not None


def test_curriculum_path_multi_step_writes_are_atomic(db) -> None:
    _, _, _, module = create_hierarchy(db)
    lesson = create_lesson(
        db,
        {
            "module_id": module.id,
            "title": "Markets",
            "slug": "markets",
        },
    )

    with pytest.raises(ResourceNotFoundError):
        create_curriculum_path(
            db,
            {
                "name": "Invalid Path",
                "slug": "invalid-path",
                "lesson_ids": [lesson.id, 9999],
            },
        )
    assert get_curriculum_path_by_slug(db, "invalid-path") is None

    path = create_curriculum_path(
        db,
        {"name": "Valid Path", "slug": "valid-path"},
    )
    with pytest.raises(ResourceNotFoundError):
        update_curriculum_path(
            db,
            path.id,
            {"name": "Partially Updated", "lesson_ids": [9999]},
        )
    db.refresh(path)
    assert path.name == "Valid Path"

