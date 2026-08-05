from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Concept,
    Course,
    CurriculumPath,
    CurriculumPathLesson,
    Degree,
    KnowledgeArticle,
    LearningObjective,
    Lesson,
    LessonPrerequisite,
    Module,
    School,
)
from ..models.enums import DifficultyLevel, KnowledgeLifecycleStatus
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)
from .knowledge_articles import normalize_slug


ModelT = TypeVar("ModelT")


def _data(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value.value if isinstance(value, Enum) else value
        for key, value in values.items()
    }


def _commit(
    db: Session,
    *,
    conflict_message: str,
    commit: bool,
) -> None:
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def _get(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise ResourceNotFoundError(model.__name__, item_id)
    return item


def _required(
    data: Mapping[str, Any],
    fields: set[str],
    entity_name: str,
    *,
    creating: bool,
) -> None:
    missing = sorted(
        field
        for field in fields
        if (creating and field not in data) or data.get(field) is None
    )
    if missing:
        raise ResourceValidationError(
            f"{entity_name} requires non-null fields: {', '.join(missing)}"
        )


def _validate_nonnegative(
    data: Mapping[str, Any],
    fields: Sequence[str],
) -> None:
    for field in fields:
        value = data.get(field)
        if value is not None and value < 0:
            raise ResourceValidationError(f"{field} must be non-negative")


def _validate_enum(
    field: str,
    value: Any,
    enum_type: type[Enum],
) -> None:
    if value is None:
        return
    allowed = {member.value for member in enum_type}
    if value not in allowed:
        raise ResourceValidationError(
            f"{field} must be one of: {', '.join(sorted(allowed))}"
        )


def _validate_foreign_keys(
    db: Session,
    data: Mapping[str, Any],
    foreign_keys: Mapping[str, type],
) -> None:
    for field, model in foreign_keys.items():
        if field not in data or data[field] is None:
            continue
        if db.get(model, data[field]) is None:
            raise ResourceNotFoundError(model.__name__, data[field])


def _validate_slug(
    db: Session,
    model: type,
    slug: str,
    *,
    item_id: int | None = None,
) -> None:
    conditions = [model.slug == slug]
    if item_id is not None:
        conditions.append(model.id != item_id)
    existing = db.scalar(select(model.id).where(*conditions))
    if existing is not None:
        raise ResourceConflictError(f"{model.__name__} slug already exists")


def _prepare_slug(
    db: Session,
    model: type,
    data: dict[str, Any],
    *,
    source_field: str,
    item_id: int | None = None,
) -> None:
    if "slug" not in data and item_id is not None:
        return
    source = data.get("slug") or data.get(source_field)
    if source is None:
        raise ResourceValidationError(
            f"{model.__name__} requires a slug or {source_field}"
        )
    data["slug"] = normalize_slug(source)
    _validate_slug(db, model, data["slug"], item_id=item_id)


def _create_entity(
    db: Session,
    model: type[ModelT],
    values: Mapping[str, Any],
    *,
    required_fields: set[str],
    foreign_keys: Mapping[str, type] | None = None,
    nonnegative_fields: Sequence[str] = (),
    slug_source: str | None = None,
    commit: bool,
) -> ModelT:
    data = _data(values)
    if slug_source is not None:
        _prepare_slug(db, model, data, source_field=slug_source)
    _required(data, required_fields, model.__name__, creating=True)
    _validate_nonnegative(data, nonnegative_fields)
    _validate_foreign_keys(db, data, foreign_keys or {})
    item = model(**data)
    db.add(item)
    _commit(
        db,
        conflict_message=f"{model.__name__} could not be created",
        commit=commit,
    )
    return item


def _update_entity(
    db: Session,
    model: type[ModelT],
    item_id: int,
    values: Mapping[str, Any],
    *,
    required_fields: set[str],
    foreign_keys: Mapping[str, type] | None = None,
    nonnegative_fields: Sequence[str] = (),
    slug_source: str | None = None,
    commit: bool,
) -> ModelT:
    item = _get(db, model, item_id)
    data = _data(values)
    if not data:
        return item
    _required(data, required_fields & data.keys(), model.__name__, creating=False)
    if slug_source is not None:
        _prepare_slug(
            db,
            model,
            data,
            source_field=slug_source,
            item_id=item_id,
        )
    _validate_nonnegative(data, nonnegative_fields)
    _validate_foreign_keys(db, data, foreign_keys or {})
    for field, value in data.items():
        setattr(item, field, value)
    _commit(
        db,
        conflict_message=f"{model.__name__} could not be updated",
        commit=commit,
    )
    return item


def _delete_entity(
    db: Session,
    model: type,
    item_id: int,
    *,
    commit: bool,
) -> None:
    db.delete(_get(db, model, item_id))
    _commit(
        db,
        conflict_message=f"{model.__name__} could not be deleted",
        commit=commit,
    )


def _paginate(statement, *, skip: int, limit: int | None):
    if skip < 0:
        raise ResourceValidationError("skip must be non-negative")
    statement = statement.offset(skip)
    if limit is not None:
        if limit < 1:
            raise ResourceValidationError("limit must be at least 1")
        statement = statement.limit(limit)
    return statement


def create_school(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> School:
    return _create_entity(
        db,
        School,
        values,
        required_fields={"name"},
        nonnegative_fields=("display_order",),
        slug_source="name",
        commit=commit,
    )


def get_school(db: Session, school_id: int) -> School:
    lesson_loader = (
        selectinload(School.degrees)
        .selectinload(Degree.courses)
        .selectinload(Course.modules)
        .selectinload(Module.lessons)
    )
    school = db.scalar(
        select(School)
        .where(School.id == school_id)
        .options(
            lesson_loader.selectinload(Lesson.objectives),
            lesson_loader.selectinload(Lesson.prerequisite_links),
            lesson_loader.selectinload(Lesson.dependent_links),
            lesson_loader.selectinload(Lesson.curriculum_path_links),
        )
        .execution_options(populate_existing=True)
    )
    if school is None:
        raise ResourceNotFoundError("School", school_id)
    return school


def get_school_by_slug(db: Session, slug: str) -> School | None:
    return db.scalar(
        select(School).where(School.slug == normalize_slug(slug))
    )


def list_schools(
    db: Session,
    *,
    active_only: bool = False,
    skip: int = 0,
    limit: int | None = None,
) -> list[School]:
    statement = select(School)
    if active_only:
        statement = statement.where(School.is_active.is_(True))
    statement = statement.order_by(School.display_order, School.id)
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_school(
    db: Session,
    school_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> School:
    return _update_entity(
        db,
        School,
        school_id,
        values,
        required_fields={"name", "slug", "display_order", "is_active"},
        nonnegative_fields=("display_order",),
        slug_source="name",
        commit=commit,
    )


def delete_school(
    db: Session,
    school_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_school(db, school_id))
    _commit(
        db,
        conflict_message="School could not be deleted",
        commit=commit,
    )


def create_degree(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Degree:
    return _create_entity(
        db,
        Degree,
        values,
        required_fields={"school_id", "name", "level"},
        foreign_keys={"school_id": School},
        nonnegative_fields=("estimated_hours", "display_order"),
        slug_source="name",
        commit=commit,
    )


def get_degree(db: Session, degree_id: int) -> Degree:
    lesson_loader = (
        selectinload(Degree.courses)
        .selectinload(Course.modules)
        .selectinload(Module.lessons)
    )
    degree = db.scalar(
        select(Degree)
        .where(Degree.id == degree_id)
        .options(
            lesson_loader.selectinload(Lesson.objectives),
            lesson_loader.selectinload(Lesson.prerequisite_links),
            lesson_loader.selectinload(Lesson.dependent_links),
            lesson_loader.selectinload(Lesson.curriculum_path_links),
        )
        .execution_options(populate_existing=True)
    )
    if degree is None:
        raise ResourceNotFoundError("Degree", degree_id)
    return degree


def get_degree_by_slug(db: Session, slug: str) -> Degree | None:
    return db.scalar(
        select(Degree).where(Degree.slug == normalize_slug(slug))
    )


def list_degrees(
    db: Session,
    *,
    school_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[Degree]:
    statement = select(Degree)
    if school_id is not None:
        statement = statement.where(Degree.school_id == school_id)
    statement = statement.order_by(Degree.display_order, Degree.id)
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_degree(
    db: Session,
    degree_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Degree:
    return _update_entity(
        db,
        Degree,
        degree_id,
        values,
        required_fields={
            "school_id",
            "name",
            "slug",
            "level",
            "estimated_hours",
            "display_order",
        },
        foreign_keys={"school_id": School},
        nonnegative_fields=("estimated_hours", "display_order"),
        slug_source="name",
        commit=commit,
    )


def delete_degree(
    db: Session,
    degree_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_degree(db, degree_id))
    _commit(
        db,
        conflict_message="Degree could not be deleted",
        commit=commit,
    )


def create_course(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Course:
    return _create_entity(
        db,
        Course,
        values,
        required_fields={"degree_id", "name"},
        foreign_keys={"degree_id": Degree},
        nonnegative_fields=("estimated_hours", "display_order"),
        slug_source="name",
        commit=commit,
    )


def get_course(db: Session, course_id: int) -> Course:
    lesson_loader = (
        selectinload(Course.modules).selectinload(Module.lessons)
    )
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            lesson_loader.selectinload(Lesson.objectives),
            lesson_loader.selectinload(Lesson.prerequisite_links),
            lesson_loader.selectinload(Lesson.dependent_links),
            lesson_loader.selectinload(Lesson.curriculum_path_links),
        )
        .execution_options(populate_existing=True)
    )
    if course is None:
        raise ResourceNotFoundError("Course", course_id)
    return course


def get_course_by_slug(db: Session, slug: str) -> Course | None:
    return db.scalar(
        select(Course).where(Course.slug == normalize_slug(slug))
    )


def list_courses(
    db: Session,
    *,
    degree_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[Course]:
    statement = select(Course)
    if degree_id is not None:
        statement = statement.where(Course.degree_id == degree_id)
    statement = statement.order_by(Course.display_order, Course.id)
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_course(
    db: Session,
    course_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Course:
    return _update_entity(
        db,
        Course,
        course_id,
        values,
        required_fields={
            "degree_id",
            "name",
            "slug",
            "estimated_hours",
            "display_order",
        },
        foreign_keys={"degree_id": Degree},
        nonnegative_fields=("estimated_hours", "display_order"),
        slug_source="name",
        commit=commit,
    )


def delete_course(
    db: Session,
    course_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_course(db, course_id))
    _commit(
        db,
        conflict_message="Course could not be deleted",
        commit=commit,
    )


def create_module(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Module:
    return _create_entity(
        db,
        Module,
        values,
        required_fields={"course_id", "name"},
        foreign_keys={"course_id": Course},
        nonnegative_fields=("estimated_minutes", "display_order"),
        slug_source="name",
        commit=commit,
    )


def get_module(db: Session, module_id: int) -> Module:
    lesson_loader = selectinload(Module.lessons)
    module = db.scalar(
        select(Module)
        .where(Module.id == module_id)
        .options(
            lesson_loader.selectinload(Lesson.objectives),
            lesson_loader.selectinload(Lesson.prerequisite_links),
            lesson_loader.selectinload(Lesson.dependent_links),
            lesson_loader.selectinload(Lesson.curriculum_path_links),
        )
        .execution_options(populate_existing=True)
    )
    if module is None:
        raise ResourceNotFoundError("Module", module_id)
    return module


def get_module_by_slug(db: Session, slug: str) -> Module | None:
    return db.scalar(
        select(Module).where(Module.slug == normalize_slug(slug))
    )


def list_modules(
    db: Session,
    *,
    course_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[Module]:
    statement = select(Module)
    if course_id is not None:
        statement = statement.where(Module.course_id == course_id)
    statement = statement.order_by(Module.display_order, Module.id)
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_module(
    db: Session,
    module_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Module:
    return _update_entity(
        db,
        Module,
        module_id,
        values,
        required_fields={
            "course_id",
            "name",
            "slug",
            "estimated_minutes",
            "display_order",
        },
        foreign_keys={"course_id": Course},
        nonnegative_fields=("estimated_minutes", "display_order"),
        slug_source="name",
        commit=commit,
    )


def delete_module(
    db: Session,
    module_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_module(db, module_id))
    _commit(
        db,
        conflict_message="Module could not be deleted",
        commit=commit,
    )


def _validate_lesson_values(data: Mapping[str, Any]) -> None:
    _validate_nonnegative(data, ("estimated_minutes", "display_order"))
    _validate_enum(
        "difficulty_level",
        data.get("difficulty_level"),
        DifficultyLevel,
    )
    _validate_enum(
        "status",
        data.get("status"),
        KnowledgeLifecycleStatus,
    )


def create_lesson(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Lesson:
    data = _data(values)
    _prepare_slug(db, Lesson, data, source_field="title")
    _required(data, {"module_id", "title"}, "Lesson", creating=True)
    _validate_lesson_values(data)
    _validate_foreign_keys(
        db,
        data,
        {
            "module_id": Module,
            "knowledge_article_id": KnowledgeArticle,
            "concept_id": Concept,
        },
    )
    lesson = Lesson(**data)
    db.add(lesson)
    _commit(
        db,
        conflict_message="Lesson could not be created",
        commit=commit,
    )
    return get_lesson(db, lesson.id)


def get_lesson(db: Session, lesson_id: int) -> Lesson:
    lesson = db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.objectives),
            selectinload(Lesson.prerequisite_links),
            selectinload(Lesson.dependent_links),
            selectinload(Lesson.curriculum_path_links),
        )
        .execution_options(populate_existing=True)
    )
    if lesson is None:
        raise ResourceNotFoundError("Lesson", lesson_id)
    return lesson


def get_lesson_by_slug(db: Session, slug: str) -> Lesson | None:
    return db.scalar(
        select(Lesson).where(Lesson.slug == normalize_slug(slug))
    )


def list_lessons(
    db: Session,
    *,
    module_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[Lesson]:
    statement = select(Lesson)
    if module_id is not None:
        statement = statement.where(Lesson.module_id == module_id)
    statement = statement.order_by(Lesson.display_order, Lesson.id)
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_lesson(
    db: Session,
    lesson_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Lesson:
    lesson = get_lesson(db, lesson_id)
    data = _data(values)
    if not data:
        return lesson
    _required(
        data,
        {
            "module_id",
            "title",
            "slug",
            "estimated_minutes",
            "difficulty_level",
            "status",
            "display_order",
        }
        & data.keys(),
        "Lesson",
        creating=False,
    )
    _prepare_slug(
        db,
        Lesson,
        data,
        source_field="title",
        item_id=lesson_id,
    )
    _validate_lesson_values(data)
    _validate_foreign_keys(
        db,
        data,
        {
            "module_id": Module,
            "knowledge_article_id": KnowledgeArticle,
            "concept_id": Concept,
        },
    )
    for field, value in data.items():
        setattr(lesson, field, value)
    _commit(
        db,
        conflict_message="Lesson could not be updated",
        commit=commit,
    )
    return get_lesson(db, lesson_id)


def delete_lesson(
    db: Session,
    lesson_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_lesson(db, lesson_id))
    _commit(
        db,
        conflict_message="Lesson could not be deleted",
        commit=commit,
    )


def create_learning_objective(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> LearningObjective:
    return _create_entity(
        db,
        LearningObjective,
        values,
        required_fields={"lesson_id", "objective"},
        foreign_keys={"lesson_id": Lesson},
        nonnegative_fields=("display_order",),
        commit=commit,
    )


def get_learning_objective(
    db: Session,
    objective_id: int,
) -> LearningObjective:
    return _get(db, LearningObjective, objective_id)


def list_learning_objectives(
    db: Session,
    *,
    lesson_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[LearningObjective]:
    statement = select(LearningObjective)
    if lesson_id is not None:
        statement = statement.where(LearningObjective.lesson_id == lesson_id)
    statement = statement.order_by(
        LearningObjective.display_order,
        LearningObjective.id,
    )
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_learning_objective(
    db: Session,
    objective_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> LearningObjective:
    return _update_entity(
        db,
        LearningObjective,
        objective_id,
        values,
        required_fields={"lesson_id", "objective", "display_order"},
        foreign_keys={"lesson_id": Lesson},
        nonnegative_fields=("display_order",),
        commit=commit,
    )


def delete_learning_objective(
    db: Session,
    objective_id: int,
    *,
    commit: bool = True,
) -> None:
    _delete_entity(db, LearningObjective, objective_id, commit=commit)


def _validate_prerequisite_pair(
    db: Session,
    lesson_id: int,
    prerequisite_lesson_id: int,
    *,
    exclude_id: int | None = None,
) -> None:
    _get(db, Lesson, lesson_id)
    _get(db, Lesson, prerequisite_lesson_id)
    if lesson_id == prerequisite_lesson_id:
        raise ResourceValidationError(
            "A lesson cannot be its own prerequisite"
        )

    duplicate_conditions = [
        LessonPrerequisite.lesson_id == lesson_id,
        LessonPrerequisite.prerequisite_lesson_id
        == prerequisite_lesson_id,
    ]
    if exclude_id is not None:
        duplicate_conditions.append(LessonPrerequisite.id != exclude_id)
    if db.scalar(
        select(LessonPrerequisite.id).where(*duplicate_conditions)
    ) is not None:
        raise ResourceConflictError("Lesson prerequisite already exists")

    graph: dict[int, set[int]] = defaultdict(set)
    statement = select(
        LessonPrerequisite.id,
        LessonPrerequisite.lesson_id,
        LessonPrerequisite.prerequisite_lesson_id,
    )
    for edge_id, dependent_id, required_id in db.execute(statement):
        if edge_id != exclude_id:
            graph[dependent_id].add(required_id)
    graph[lesson_id].add(prerequisite_lesson_id)

    pending = [prerequisite_lesson_id]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if current == lesson_id:
            raise ResourceValidationError(
                "Lesson prerequisites cannot contain a cycle"
            )
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph[current] - visited)


def create_lesson_prerequisite(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> LessonPrerequisite:
    data = _data(values)
    _required(
        data,
        {"lesson_id", "prerequisite_lesson_id"},
        "LessonPrerequisite",
        creating=True,
    )
    _validate_prerequisite_pair(
        db,
        data["lesson_id"],
        data["prerequisite_lesson_id"],
    )
    prerequisite = LessonPrerequisite(**data)
    db.add(prerequisite)
    _commit(
        db,
        conflict_message="Lesson prerequisite could not be created",
        commit=commit,
    )
    return prerequisite


def get_lesson_prerequisite(
    db: Session,
    prerequisite_id: int,
) -> LessonPrerequisite:
    return _get(db, LessonPrerequisite, prerequisite_id)


def list_lesson_prerequisites(
    db: Session,
    *,
    lesson_id: int | None = None,
    prerequisite_lesson_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[LessonPrerequisite]:
    statement = select(LessonPrerequisite)
    if lesson_id is not None:
        statement = statement.where(
            LessonPrerequisite.lesson_id == lesson_id
        )
    if prerequisite_lesson_id is not None:
        statement = statement.where(
            LessonPrerequisite.prerequisite_lesson_id
            == prerequisite_lesson_id
        )
    statement = statement.order_by(LessonPrerequisite.id)
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_lesson_prerequisite(
    db: Session,
    prerequisite_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> LessonPrerequisite:
    prerequisite = get_lesson_prerequisite(db, prerequisite_id)
    data = _data(values)
    if not data:
        return prerequisite
    _required(
        data,
        {"lesson_id", "prerequisite_lesson_id"} & data.keys(),
        "LessonPrerequisite",
        creating=False,
    )
    lesson_id = data.get("lesson_id", prerequisite.lesson_id)
    prerequisite_lesson_id = data.get(
        "prerequisite_lesson_id",
        prerequisite.prerequisite_lesson_id,
    )
    _validate_prerequisite_pair(
        db,
        lesson_id,
        prerequisite_lesson_id,
        exclude_id=prerequisite_id,
    )
    prerequisite.lesson_id = lesson_id
    prerequisite.prerequisite_lesson_id = prerequisite_lesson_id
    _commit(
        db,
        conflict_message="Lesson prerequisite could not be updated",
        commit=commit,
    )
    return prerequisite


def delete_lesson_prerequisite(
    db: Session,
    prerequisite_id: int,
    *,
    commit: bool = True,
) -> None:
    _delete_entity(
        db,
        LessonPrerequisite,
        prerequisite_id,
        commit=commit,
    )


def create_curriculum_path(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> CurriculumPath:
    data = _data(values)
    lesson_ids = data.pop("lesson_ids", None)
    try:
        path = _create_entity(
            db,
            CurriculumPath,
            data,
            required_fields={"name"},
            slug_source="name",
            commit=False if lesson_ids is not None else commit,
        )
        if lesson_ids is not None:
            _replace_curriculum_path_lessons(db, path, lesson_ids)
            _commit(
                db,
                conflict_message="CurriculumPath could not be created",
                commit=commit,
            )
    except Exception:
        db.rollback()
        raise
    return get_curriculum_path(db, path.id)


def get_curriculum_path(
    db: Session,
    path_id: int,
) -> CurriculumPath:
    path = db.scalar(
        select(CurriculumPath)
        .where(CurriculumPath.id == path_id)
        .options(
            selectinload(CurriculumPath.lesson_links).selectinload(
                CurriculumPathLesson.lesson
            )
        )
        .execution_options(populate_existing=True)
    )
    if path is None:
        raise ResourceNotFoundError("CurriculumPath", path_id)
    return path


def get_curriculum_path_by_slug(
    db: Session,
    slug: str,
) -> CurriculumPath | None:
    return db.scalar(
        select(CurriculumPath).where(
            CurriculumPath.slug == normalize_slug(slug)
        )
    )


def list_curriculum_paths(
    db: Session,
    *,
    skip: int = 0,
    limit: int | None = None,
) -> list[CurriculumPath]:
    statement = select(CurriculumPath).order_by(
        CurriculumPath.name,
        CurriculumPath.id,
    )
    return list(db.scalars(_paginate(statement, skip=skip, limit=limit)))


def update_curriculum_path(
    db: Session,
    path_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> CurriculumPath:
    data = _data(values)
    lesson_ids = data.pop("lesson_ids", None)
    try:
        path = _update_entity(
            db,
            CurriculumPath,
            path_id,
            data,
            required_fields={"name", "slug"},
            slug_source="name",
            commit=False if lesson_ids is not None else commit,
        )
        if lesson_ids is not None:
            _replace_curriculum_path_lessons(db, path, lesson_ids)
            _commit(
                db,
                conflict_message="CurriculumPath could not be updated",
                commit=commit,
            )
    except Exception:
        db.rollback()
        raise
    return get_curriculum_path(db, path_id)


def delete_curriculum_path(
    db: Session,
    path_id: int,
    *,
    commit: bool = True,
) -> None:
    _delete_entity(db, CurriculumPath, path_id, commit=commit)


def create_curriculum_path_lesson(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> CurriculumPathLesson:
    data = _data(values)
    _required(
        data,
        {"curriculum_path_id", "lesson_id", "display_order"},
        "CurriculumPathLesson",
        creating=True,
    )
    _validate_nonnegative(data, ("display_order",))
    _validate_foreign_keys(
        db,
        data,
        {"curriculum_path_id": CurriculumPath, "lesson_id": Lesson},
    )
    link = CurriculumPathLesson(**data)
    db.add(link)
    _commit(
        db,
        conflict_message="Curriculum path lesson or order already exists",
        commit=commit,
    )
    return link


def get_curriculum_path_lesson(
    db: Session,
    path_id: int,
    lesson_id: int,
) -> CurriculumPathLesson:
    link = db.get(CurriculumPathLesson, (path_id, lesson_id))
    if link is None:
        raise ResourceNotFoundError(
            "CurriculumPathLesson",
            f"{path_id}:{lesson_id}",
        )
    return link


def list_curriculum_path_lessons(
    db: Session,
    path_id: int,
) -> list[CurriculumPathLesson]:
    _get(db, CurriculumPath, path_id)
    return list(
        db.scalars(
            select(CurriculumPathLesson)
            .where(CurriculumPathLesson.curriculum_path_id == path_id)
            .order_by(
                CurriculumPathLesson.display_order,
                CurriculumPathLesson.lesson_id,
            )
        )
    )


def update_curriculum_path_lesson(
    db: Session,
    path_id: int,
    lesson_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> CurriculumPathLesson:
    link = get_curriculum_path_lesson(db, path_id, lesson_id)
    data = _data(values)
    if not data:
        return link
    _required(
        data,
        {
            "curriculum_path_id",
            "lesson_id",
            "display_order",
        }
        & data.keys(),
        "CurriculumPathLesson",
        creating=False,
    )
    _validate_nonnegative(data, ("display_order",))
    _validate_foreign_keys(
        db,
        data,
        {"curriculum_path_id": CurriculumPath, "lesson_id": Lesson},
    )
    for field, value in data.items():
        setattr(link, field, value)
    _commit(
        db,
        conflict_message="Curriculum path lesson or order already exists",
        commit=commit,
    )
    return link


def delete_curriculum_path_lesson(
    db: Session,
    path_id: int,
    lesson_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_curriculum_path_lesson(db, path_id, lesson_id))
    _commit(
        db,
        conflict_message="Curriculum path lesson could not be deleted",
        commit=commit,
    )


def add_lesson_to_curriculum_path(
    db: Session,
    path_id: int,
    lesson_id: int,
    *,
    display_order: int | None = None,
    commit: bool = True,
) -> CurriculumPathLesson:
    _get(db, CurriculumPath, path_id)
    _get(db, Lesson, lesson_id)
    if display_order is None:
        maximum = db.scalar(
            select(func.max(CurriculumPathLesson.display_order)).where(
                CurriculumPathLesson.curriculum_path_id == path_id
            )
        )
        display_order = 0 if maximum is None else maximum + 1
    return create_curriculum_path_lesson(
        db,
        {
            "curriculum_path_id": path_id,
            "lesson_id": lesson_id,
            "display_order": display_order,
        },
        commit=commit,
    )


def remove_lesson_from_curriculum_path(
    db: Session,
    path_id: int,
    lesson_id: int,
    *,
    commit: bool = True,
) -> None:
    delete_curriculum_path_lesson(
        db,
        path_id,
        lesson_id,
        commit=commit,
    )


def _replace_curriculum_path_lessons(
    db: Session,
    path: CurriculumPath,
    lesson_ids: Sequence[int],
) -> None:
    ordered_ids = list(lesson_ids)
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ResourceConflictError(
            "Curriculum path lessons must be unique"
        )
    for lesson_id in ordered_ids:
        _get(db, Lesson, lesson_id)
    db.execute(
        delete(CurriculumPathLesson).where(
            CurriculumPathLesson.curriculum_path_id == path.id
        )
    )
    db.flush()
    db.add_all(
        CurriculumPathLesson(
            curriculum_path_id=path.id,
            lesson_id=lesson_id,
            display_order=position,
        )
        for position, lesson_id in enumerate(ordered_ids)
    )
    db.flush()
    db.expire(path, ["lesson_links", "lessons"])


def replace_curriculum_path_lessons(
    db: Session,
    path_id: int,
    lesson_ids: Sequence[int],
    *,
    commit: bool = True,
) -> CurriculumPath:
    path = get_curriculum_path(db, path_id)
    _replace_curriculum_path_lessons(db, path, lesson_ids)
    _commit(
        db,
        conflict_message="Curriculum path lessons could not be replaced",
        commit=commit,
    )
    return get_curriculum_path(db, path_id)


add_lesson_to_path = add_lesson_to_curriculum_path
remove_lesson_from_path = remove_lesson_from_curriculum_path
list_path_lessons = list_curriculum_path_lessons
replace_path_lessons = replace_curriculum_path_lessons


__all__ = [
    "add_lesson_to_curriculum_path",
    "add_lesson_to_path",
    "create_course",
    "create_curriculum_path",
    "create_curriculum_path_lesson",
    "create_degree",
    "create_learning_objective",
    "create_lesson",
    "create_lesson_prerequisite",
    "create_module",
    "create_school",
    "delete_course",
    "delete_curriculum_path",
    "delete_curriculum_path_lesson",
    "delete_degree",
    "delete_learning_objective",
    "delete_lesson",
    "delete_lesson_prerequisite",
    "delete_module",
    "delete_school",
    "get_course",
    "get_course_by_slug",
    "get_curriculum_path",
    "get_curriculum_path_by_slug",
    "get_curriculum_path_lesson",
    "get_degree",
    "get_degree_by_slug",
    "get_learning_objective",
    "get_lesson",
    "get_lesson_by_slug",
    "get_lesson_prerequisite",
    "get_module",
    "get_module_by_slug",
    "get_school",
    "get_school_by_slug",
    "list_courses",
    "list_curriculum_path_lessons",
    "list_curriculum_paths",
    "list_degrees",
    "list_learning_objectives",
    "list_lesson_prerequisites",
    "list_lessons",
    "list_modules",
    "list_path_lessons",
    "list_schools",
    "remove_lesson_from_curriculum_path",
    "remove_lesson_from_path",
    "replace_curriculum_path_lessons",
    "replace_path_lessons",
    "update_course",
    "update_curriculum_path",
    "update_curriculum_path_lesson",
    "update_degree",
    "update_learning_objective",
    "update_lesson",
    "update_lesson_prerequisite",
    "update_module",
    "update_school",
]
