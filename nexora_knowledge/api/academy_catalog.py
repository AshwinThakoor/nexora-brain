from __future__ import annotations

from typing import Any, TypeVar

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Course,
    CurriculumPath,
    Degree,
    KnowledgeLifecycleStatus,
    Lesson,
    Module,
    School,
)
from ..schemas.api_curriculum import (
    AcademyPage,
    CourseDetail,
    CourseSummary,
    CurriculumPathDetail,
    CurriculumPathSummary,
    DegreeDetail,
    DegreeSummary,
    LessonDetail,
    LessonSummary,
    ModuleDetail,
    ModuleSummary,
    SchoolDetail,
    SchoolSummary,
)
from ..services.authorization import Principal
from ..services.exceptions import ResourceNotFoundError
from .dependencies import get_current_principal, get_db


router = APIRouter(
    prefix="/api/v1/academy/catalog",
    tags=["academy-catalog"],
)
ModelT = TypeVar("ModelT")


def _auth(principal: Principal) -> None:
    del principal


def _offset(offset: int, skip: int | None) -> int:
    return skip if skip is not None else offset


def _page(
    db: Session,
    statement,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Any], int]:
    total = db.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    items = list(db.scalars(statement.offset(offset).limit(limit)))
    return items, int(total or 0)


def _response_page(
    items: list[Any],
    total: int,
    *,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "skip": offset,
    }


def _active_hierarchy():
    return School.is_active.is_(True)


@router.get("/schools", response_model=AcademyPage[SchoolSummary])
def list_schools(
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    statement = select(School).where(_active_hierarchy())
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(School.name).like(term),
                func.lower(School.slug).like(term),
            )
        )
    statement = statement.order_by(School.display_order, School.id)
    resolved_offset = _offset(offset, skip)
    items, total = _page(
        db, statement, limit=limit, offset=resolved_offset
    )
    return _response_page(
        items, total, limit=limit, offset=resolved_offset
    )


@router.get("/schools/{school_id}", response_model=SchoolDetail)
def get_school(
    school_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    school = db.scalar(
        select(School)
        .where(School.id == school_id, _active_hierarchy())
        .options(selectinload(School.degrees))
    )
    if school is None:
        raise ResourceNotFoundError("School", school_id)
    return school


@router.get("/degrees", response_model=AcademyPage[DegreeSummary])
def list_degrees(
    school_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    statement = (
        select(Degree)
        .join(School, School.id == Degree.school_id)
        .where(_active_hierarchy())
    )
    if school_id is not None:
        statement = statement.where(Degree.school_id == school_id)
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Degree.name).like(term),
                func.lower(Degree.slug).like(term),
            )
        )
    statement = statement.order_by(
        Degree.school_id, Degree.display_order, Degree.id
    )
    resolved_offset = _offset(offset, skip)
    items, total = _page(
        db, statement, limit=limit, offset=resolved_offset
    )
    return _response_page(
        items, total, limit=limit, offset=resolved_offset
    )


@router.get("/degrees/{degree_id}", response_model=DegreeDetail)
def get_degree(
    degree_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    degree = db.scalar(
        select(Degree)
        .join(School, School.id == Degree.school_id)
        .where(Degree.id == degree_id, _active_hierarchy())
        .options(selectinload(Degree.courses))
    )
    if degree is None:
        raise ResourceNotFoundError("Degree", degree_id)
    return degree


@router.get("/courses", response_model=AcademyPage[CourseSummary])
def list_courses(
    degree_id: int | None = Query(default=None, gt=0),
    school_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    statement = (
        select(Course)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(_active_hierarchy())
    )
    if degree_id is not None:
        statement = statement.where(Course.degree_id == degree_id)
    if school_id is not None:
        statement = statement.where(Degree.school_id == school_id)
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Course.name).like(term),
                func.lower(Course.slug).like(term),
            )
        )
    statement = statement.order_by(
        Course.degree_id, Course.display_order, Course.id
    )
    resolved_offset = _offset(offset, skip)
    items, total = _page(
        db, statement, limit=limit, offset=resolved_offset
    )
    return _response_page(
        items, total, limit=limit, offset=resolved_offset
    )


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(
    course_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    course = db.scalar(
        select(Course)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(Course.id == course_id, _active_hierarchy())
        .options(selectinload(Course.modules))
    )
    if course is None:
        raise ResourceNotFoundError("Course", course_id)
    return course


@router.get("/modules", response_model=AcademyPage[ModuleSummary])
def list_modules(
    course_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    statement = (
        select(Module)
        .join(Course, Course.id == Module.course_id)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(_active_hierarchy())
    )
    if course_id is not None:
        statement = statement.where(Module.course_id == course_id)
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Module.name).like(term),
                func.lower(Module.slug).like(term),
            )
        )
    statement = statement.order_by(
        Module.course_id, Module.display_order, Module.id
    )
    resolved_offset = _offset(offset, skip)
    items, total = _page(
        db, statement, limit=limit, offset=resolved_offset
    )
    return _response_page(
        items, total, limit=limit, offset=resolved_offset
    )


@router.get("/modules/{module_id}", response_model=ModuleDetail)
def get_module(
    module_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    module = db.scalar(
        select(Module)
        .join(Course, Course.id == Module.course_id)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(Module.id == module_id, _active_hierarchy())
        .options(
            selectinload(Module.lessons.and_(
                Lesson.status == KnowledgeLifecycleStatus.PUBLISHED.value
            ))
        )
    )
    if module is None:
        raise ResourceNotFoundError("Module", module_id)
    return module


@router.get("/lessons", response_model=AcademyPage[LessonSummary])
def list_lessons(
    module_id: int | None = Query(default=None, gt=0),
    course_id: int | None = Query(default=None, gt=0),
    difficulty: str | None = Query(default=None, max_length=50),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    statement = (
        select(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(
            _active_hierarchy(),
            Lesson.status == KnowledgeLifecycleStatus.PUBLISHED.value,
        )
    )
    if module_id is not None:
        statement = statement.where(Lesson.module_id == module_id)
    if course_id is not None:
        statement = statement.where(Module.course_id == course_id)
    if difficulty is not None:
        statement = statement.where(Lesson.difficulty_level == difficulty)
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Lesson.title).like(term),
                func.lower(Lesson.slug).like(term),
            )
        )
    statement = statement.order_by(
        Module.course_id,
        Module.display_order,
        Module.id,
        Lesson.display_order,
        Lesson.id,
    )
    resolved_offset = _offset(offset, skip)
    items, total = _page(
        db, statement, limit=limit, offset=resolved_offset
    )
    return _response_page(
        items, total, limit=limit, offset=resolved_offset
    )


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
def get_lesson(
    lesson_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    lesson = db.scalar(
        select(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(
            Lesson.id == lesson_id,
            Lesson.status == KnowledgeLifecycleStatus.PUBLISHED.value,
            _active_hierarchy(),
        )
        .options(
            selectinload(Lesson.objectives),
            selectinload(
                Lesson.prerequisites.and_(
                    Lesson.status
                    == KnowledgeLifecycleStatus.PUBLISHED.value
                )
            ),
        )
    )
    if lesson is None:
        raise ResourceNotFoundError("Lesson", lesson_id)
    return lesson


@router.get(
    "/curriculum-paths",
    response_model=AcademyPage[CurriculumPathSummary],
)
def list_curriculum_paths(
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    statement = select(CurriculumPath)
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(CurriculumPath.name).like(term),
                func.lower(CurriculumPath.slug).like(term),
            )
        )
    statement = statement.order_by(CurriculumPath.name, CurriculumPath.id)
    resolved_offset = _offset(offset, skip)
    items, total = _page(
        db, statement, limit=limit, offset=resolved_offset
    )
    return _response_page(
        items, total, limit=limit, offset=resolved_offset
    )


@router.get(
    "/curriculum-paths/{path_id}",
    response_model=CurriculumPathDetail,
)
def get_curriculum_path(
    path_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _auth(principal)
    path = db.scalar(
        select(CurriculumPath)
        .where(CurriculumPath.id == path_id)
        .options(selectinload(CurriculumPath.lessons))
    )
    if path is None:
        raise ResourceNotFoundError("CurriculumPath", path_id)
    summary = CurriculumPathSummary.model_validate(path).model_dump()
    summary["lessons"] = [
        lesson
        for lesson in path.lessons
        if lesson.status == KnowledgeLifecycleStatus.PUBLISHED.value
    ]
    return summary


__all__ = ["router"]
