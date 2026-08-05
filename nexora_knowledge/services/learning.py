from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentOption,
    AssessmentQuestion,
    Course,
    CourseEnrollment,
    CurriculumPath,
    CurriculumPathEnrollment,
    CurriculumPathLesson,
    Learner,
    Lesson,
    LessonCompletion,
    LessonProgress,
    Module,
)
from ..models.common import utc_now
from ..models.enums import (
    AssessmentType,
    AttemptStatus,
    CompletionSource,
    EnrollmentStatus,
    GradingStatus,
    LearnerStatus,
    LessonProgressStatus,
    QuestionType,
)
from ..schemas.learning import (
    AssessmentStatistics,
    CourseProgressSummary,
    LearnerProgressSummary,
    LearnerRead,
    PathProgressSummary,
    RecentActivityItem,
)
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)
from .knowledge_articles import normalize_slug


ModelT = TypeVar("ModelT")
PERCENTAGE_DECIMALS = 2


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _data(values: Any) -> dict[str, Any]:
    if hasattr(values, "model_dump"):
        values = values.model_dump(exclude_unset=True)
    if not isinstance(values, Mapping):
        raise ResourceValidationError("values must be a mapping or schema")
    return _plain(dict(values))


def _get(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise ResourceNotFoundError(model.__name__, item_id)
    return item


def _finalize(
    db: Session,
    *,
    commit: bool,
    conflict_message: str,
) -> None:
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def _enum_value(
    field: str,
    value: Any,
    enum_type: type[Enum],
) -> str:
    if isinstance(value, enum_type):
        return value.value
    allowed = {member.value for member in enum_type}
    if value not in allowed:
        raise ResourceValidationError(
            f"{field} must be one of: {', '.join(sorted(allowed))}"
        )
    return str(value)


def _percentage(value: float) -> float:
    return round(float(value), PERCENTAGE_DECIMALS)


def _validate_percentage(value: float, field: str = "progress_percent") -> None:
    if value < 0 or value > 100:
        raise ResourceValidationError(f"{field} must be between 0 and 100")


def _validate_json(value: Any, field: str) -> None:
    if value is not None and not isinstance(value, (dict, list)):
        raise ResourceValidationError(
            f"{field} must be a JSON object, array, or null"
        )


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_external_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_identity(
    external_user_id: str | None,
    email: str | None,
) -> None:
    if external_user_id is None and email is None:
        raise ResourceValidationError(
            "Learner requires external_user_id or email"
        )
    if email is not None and (
        "@" not in email or email.startswith("@") or email.endswith("@")
    ):
        raise ResourceValidationError("email must be a valid address")


def create_learner(
    db: Session,
    values: Mapping[str, Any] | Any,
    *,
    commit: bool = True,
) -> Learner:
    data = _data(values)
    external_id = _normalize_external_id(data.get("external_user_id"))
    email = _normalize_email(data.get("email"))
    _validate_identity(external_id, email)
    display_name = str(data.get("display_name", "")).strip()
    if not display_name:
        raise ResourceValidationError("Learner requires display_name")
    status = _enum_value(
        "status",
        data.get("status", LearnerStatus.ACTIVE.value),
        LearnerStatus,
    )
    if external_id is not None and db.scalar(
        select(Learner.id).where(Learner.external_user_id == external_id)
    ) is not None:
        raise ResourceConflictError("Learner external_user_id already exists")
    if email is not None and db.scalar(
        select(Learner.id).where(func.lower(Learner.email) == email)
    ) is not None:
        raise ResourceConflictError("Learner email already exists")
    learner = Learner(
        external_user_id=external_id,
        email=email,
        display_name=display_name,
        status=status,
    )
    db.add(learner)
    _finalize(
        db,
        commit=commit,
        conflict_message="Learner identity already exists",
    )
    return learner


def get_learner(db: Session, learner_id: int) -> Learner:
    learner = db.scalar(
        select(Learner)
        .where(Learner.id == learner_id)
        .options(
            selectinload(Learner.course_enrollments),
            selectinload(Learner.curriculum_path_enrollments),
            selectinload(Learner.lesson_progress_records),
            selectinload(Learner.completion_events),
            selectinload(Learner.assessment_attempts),
        )
        .execution_options(populate_existing=True)
    )
    if learner is None:
        raise ResourceNotFoundError("Learner", learner_id)
    return learner


def update_learner(
    db: Session,
    learner_id: int,
    values: Mapping[str, Any] | Any,
    *,
    commit: bool = True,
) -> Learner:
    learner = _get(db, Learner, learner_id)
    data = _data(values)
    external_id = (
        _normalize_external_id(data["external_user_id"])
        if "external_user_id" in data
        else learner.external_user_id
    )
    email = (
        _normalize_email(data["email"])
        if "email" in data
        else learner.email
    )
    _validate_identity(external_id, email)
    if "display_name" in data:
        if data["display_name"] is None or not str(data["display_name"]).strip():
            raise ResourceValidationError("display_name cannot be empty")
        learner.display_name = str(data["display_name"]).strip()
    if "status" in data:
        learner.status = _enum_value(
            "status", data["status"], LearnerStatus
        )
    if external_id != learner.external_user_id:
        if external_id is not None and db.scalar(
            select(Learner.id).where(
                Learner.external_user_id == external_id,
                Learner.id != learner_id,
            )
        ) is not None:
            raise ResourceConflictError(
                "Learner external_user_id already exists"
            )
        learner.external_user_id = external_id
    if email != learner.email:
        if email is not None and db.scalar(
            select(Learner.id).where(
                func.lower(Learner.email) == email,
                Learner.id != learner_id,
            )
        ) is not None:
            raise ResourceConflictError("Learner email already exists")
        learner.email = email
    _finalize(
        db,
        commit=commit,
        conflict_message="Learner identity already exists",
    )
    return learner


def deactivate_learner(
    db: Session,
    learner_id: int,
    *,
    commit: bool = True,
) -> Learner:
    return update_learner(
        db,
        learner_id,
        {"status": LearnerStatus.INACTIVE.value},
        commit=commit,
    )


def _course_lesson_ids(db: Session, course_id: int) -> list[int]:
    _get(db, Course, course_id)
    return list(
        db.scalars(
            select(Lesson.id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.course_id == course_id)
            .order_by(
                Module.display_order,
                Module.id,
                Lesson.display_order,
                Lesson.id,
            )
        )
    )


def _path_lesson_ids(db: Session, path_id: int) -> list[int]:
    _get(db, CurriculumPath, path_id)
    return list(
        db.scalars(
            select(CurriculumPathLesson.lesson_id)
            .where(CurriculumPathLesson.curriculum_path_id == path_id)
            .order_by(
                CurriculumPathLesson.display_order,
                CurriculumPathLesson.lesson_id,
            )
        )
    )


def _progress_aggregate(
    db: Session,
    learner_id: int,
    lesson_ids: Sequence[int],
) -> tuple[int, int, int, datetime | None]:
    if not lesson_ids:
        return 0, 0, 0, None
    total = len(lesson_ids)
    completed, time_spent, last_accessed = db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            LessonProgress.status
                            == LessonProgressStatus.COMPLETED.value,
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(LessonProgress.time_spent_seconds), 0),
            func.max(LessonProgress.last_accessed_at),
        ).where(
            LessonProgress.learner_id == learner_id,
            LessonProgress.lesson_id.in_(lesson_ids),
        )
    ).one()
    return total, int(completed or 0), int(time_spent or 0), last_accessed


def _completion_percentage(total: int, completed: int) -> float:
    if total == 0:
        return 0.0
    return _percentage(completed * 100.0 / total)


def calculate_course_completion(
    db: Session,
    learner_id: int,
    course_id: int,
) -> float:
    _get(db, Learner, learner_id)
    total, completed, _, _ = _progress_aggregate(
        db,
        learner_id,
        _course_lesson_ids(db, course_id),
    )
    return _completion_percentage(total, completed)


def calculate_path_completion(
    db: Session,
    learner_id: int,
    curriculum_path_id: int,
) -> float:
    _get(db, Learner, learner_id)
    total, completed, _, _ = _progress_aggregate(
        db,
        learner_id,
        _path_lesson_ids(db, curriculum_path_id),
    )
    return _completion_percentage(total, completed)


def _set_enrollment_rollup(
    enrollment: CourseEnrollment | CurriculumPathEnrollment,
    *,
    total: int,
    completed: int,
    last_accessed: datetime | None,
    now: datetime,
) -> None:
    enrollment.progress_percent = _completion_percentage(total, completed)
    if last_accessed is not None:
        enrollment.last_accessed_at = last_accessed
    if total > 0 and completed == total:
        enrollment.status = EnrollmentStatus.COMPLETED.value
        enrollment.started_at = enrollment.started_at or now
        enrollment.completed_at = enrollment.completed_at or now
    elif enrollment.status == EnrollmentStatus.COMPLETED.value:
        enrollment.status = EnrollmentStatus.IN_PROGRESS.value
        enrollment.completed_at = None


def _recalculate_course_enrollment(
    db: Session,
    enrollment: CourseEnrollment,
    *,
    now: datetime,
) -> None:
    lesson_ids = _course_lesson_ids(db, enrollment.course_id)
    total, completed, _, last_accessed = _progress_aggregate(
        db, enrollment.learner_id, lesson_ids
    )
    _set_enrollment_rollup(
        enrollment,
        total=total,
        completed=completed,
        last_accessed=last_accessed,
        now=now,
    )


def _recalculate_path_enrollment(
    db: Session,
    enrollment: CurriculumPathEnrollment,
    *,
    now: datetime,
) -> None:
    lesson_ids = _path_lesson_ids(db, enrollment.curriculum_path_id)
    total, completed, _, last_accessed = _progress_aggregate(
        db, enrollment.learner_id, lesson_ids
    )
    _set_enrollment_rollup(
        enrollment,
        total=total,
        completed=completed,
        last_accessed=last_accessed,
        now=now,
    )


def _recalculate_related_enrollments(
    db: Session,
    learner_id: int,
    lesson_id: int,
    *,
    now: datetime,
) -> None:
    course_id = db.scalar(
        select(Module.course_id)
        .join(Lesson, Lesson.module_id == Module.id)
        .where(Lesson.id == lesson_id)
    )
    if course_id is not None:
        course_enrollment = db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.learner_id == learner_id,
                CourseEnrollment.course_id == course_id,
            )
        )
        if course_enrollment is not None:
            _recalculate_course_enrollment(
                db, course_enrollment, now=now
            )
    path_ids = list(
        db.scalars(
            select(CurriculumPathLesson.curriculum_path_id).where(
                CurriculumPathLesson.lesson_id == lesson_id
            )
        )
    )
    if path_ids:
        path_enrollments = db.scalars(
            select(CurriculumPathEnrollment).where(
                CurriculumPathEnrollment.learner_id == learner_id,
                CurriculumPathEnrollment.curriculum_path_id.in_(path_ids),
            )
        )
        for enrollment in path_enrollments:
            _recalculate_path_enrollment(db, enrollment, now=now)


def _require_active_learner(db: Session, learner_id: int) -> Learner:
    learner = _get(db, Learner, learner_id)
    if learner.status != LearnerStatus.ACTIVE.value:
        raise ResourceValidationError("Learner is not active")
    return learner


def enroll_in_course(
    db: Session,
    learner_id: int,
    course_id: int,
    *,
    commit: bool = True,
) -> CourseEnrollment:
    _require_active_learner(db, learner_id)
    _get(db, Course, course_id)
    if db.scalar(
        select(CourseEnrollment.id).where(
            CourseEnrollment.learner_id == learner_id,
            CourseEnrollment.course_id == course_id,
        )
    ) is not None:
        raise ResourceConflictError("Learner is already enrolled in course")
    enrollment = CourseEnrollment(
        learner_id=learner_id,
        course_id=course_id,
    )
    db.add(enrollment)
    db.flush()
    _recalculate_course_enrollment(db, enrollment, now=utc_now())
    _finalize(
        db,
        commit=commit,
        conflict_message="Learner is already enrolled in course",
    )
    return enrollment


def enroll_in_curriculum_path(
    db: Session,
    learner_id: int,
    curriculum_path_id: int,
    *,
    commit: bool = True,
) -> CurriculumPathEnrollment:
    _require_active_learner(db, learner_id)
    _get(db, CurriculumPath, curriculum_path_id)
    if db.scalar(
        select(CurriculumPathEnrollment.id).where(
            CurriculumPathEnrollment.learner_id == learner_id,
            CurriculumPathEnrollment.curriculum_path_id
            == curriculum_path_id,
        )
    ) is not None:
        raise ResourceConflictError(
            "Learner is already enrolled in curriculum path"
        )
    enrollment = CurriculumPathEnrollment(
        learner_id=learner_id,
        curriculum_path_id=curriculum_path_id,
    )
    db.add(enrollment)
    db.flush()
    _recalculate_path_enrollment(db, enrollment, now=utc_now())
    _finalize(
        db,
        commit=commit,
        conflict_message="Learner is already enrolled in curriculum path",
    )
    return enrollment


def _start_enrollment_record(
    enrollment: CourseEnrollment | CurriculumPathEnrollment,
) -> None:
    if enrollment.status == EnrollmentStatus.CANCELLED.value:
        raise ResourceValidationError("Cancelled enrollment cannot be started")
    now = utc_now()
    if enrollment.status != EnrollmentStatus.COMPLETED.value:
        enrollment.status = EnrollmentStatus.IN_PROGRESS.value
        enrollment.started_at = enrollment.started_at or now
    enrollment.last_accessed_at = now


def start_course_enrollment(
    db: Session,
    enrollment_id: int,
    *,
    commit: bool = True,
) -> CourseEnrollment:
    enrollment = _get(db, CourseEnrollment, enrollment_id)
    _start_enrollment_record(enrollment)
    _finalize(
        db,
        commit=commit,
        conflict_message="Course enrollment could not be started",
    )
    return enrollment


def start_curriculum_path_enrollment(
    db: Session,
    enrollment_id: int,
    *,
    commit: bool = True,
) -> CurriculumPathEnrollment:
    enrollment = _get(db, CurriculumPathEnrollment, enrollment_id)
    _start_enrollment_record(enrollment)
    _finalize(
        db,
        commit=commit,
        conflict_message="Curriculum path enrollment could not be started",
    )
    return enrollment


def _complete_enrollment_record(
    enrollment: CourseEnrollment | CurriculumPathEnrollment,
) -> None:
    if enrollment.status == EnrollmentStatus.CANCELLED.value:
        raise ResourceValidationError(
            "Cancelled enrollment cannot be completed"
        )
    now = utc_now()
    enrollment.status = EnrollmentStatus.COMPLETED.value
    enrollment.progress_percent = 100.0
    enrollment.started_at = enrollment.started_at or now
    enrollment.completed_at = enrollment.completed_at or now
    enrollment.last_accessed_at = now


def complete_course_enrollment(
    db: Session,
    enrollment_id: int,
    *,
    commit: bool = True,
) -> CourseEnrollment:
    enrollment = _get(db, CourseEnrollment, enrollment_id)
    _complete_enrollment_record(enrollment)
    _finalize(
        db,
        commit=commit,
        conflict_message="Course enrollment could not be completed",
    )
    return enrollment


def complete_curriculum_path_enrollment(
    db: Session,
    enrollment_id: int,
    *,
    commit: bool = True,
) -> CurriculumPathEnrollment:
    enrollment = _get(db, CurriculumPathEnrollment, enrollment_id)
    _complete_enrollment_record(enrollment)
    _finalize(
        db,
        commit=commit,
        conflict_message="Curriculum path enrollment could not be completed",
    )
    return enrollment


def start_enrollment(
    db: Session,
    enrollment: CourseEnrollment | CurriculumPathEnrollment | int,
    *,
    enrollment_type: str | None = None,
    commit: bool = True,
) -> CourseEnrollment | CurriculumPathEnrollment:
    record = _resolve_enrollment(
        db, enrollment, enrollment_type=enrollment_type
    )
    _start_enrollment_record(record)
    _finalize(
        db,
        commit=commit,
        conflict_message="Enrollment could not be started",
    )
    return record


def complete_enrollment(
    db: Session,
    enrollment: CourseEnrollment | CurriculumPathEnrollment | int,
    *,
    enrollment_type: str | None = None,
    commit: bool = True,
) -> CourseEnrollment | CurriculumPathEnrollment:
    record = _resolve_enrollment(
        db, enrollment, enrollment_type=enrollment_type
    )
    _complete_enrollment_record(record)
    _finalize(
        db,
        commit=commit,
        conflict_message="Enrollment could not be completed",
    )
    return record


def _resolve_enrollment(
    db: Session,
    enrollment: CourseEnrollment | CurriculumPathEnrollment | int,
    *,
    enrollment_type: str | None,
) -> CourseEnrollment | CurriculumPathEnrollment:
    if not isinstance(
        enrollment, (CourseEnrollment, CurriculumPathEnrollment)
    ):
        if not isinstance(enrollment, int):
            raise ResourceValidationError(
                "enrollment must be an enrollment record or integer ID"
            )
        normalized_type = (
            enrollment_type.strip().lower()
            if enrollment_type is not None
            else None
        )
        if normalized_type in {"course", "course_enrollment"}:
            return _get(db, CourseEnrollment, enrollment)
        if normalized_type in {
            "path",
            "curriculum_path",
            "curriculum_path_enrollment",
        }:
            return _get(db, CurriculumPathEnrollment, enrollment)
        if normalized_type is not None:
            raise ResourceValidationError(
                "enrollment_type must be course or curriculum_path"
            )
        matches = [
            item
            for item in (
                db.get(CourseEnrollment, enrollment),
                db.get(CurriculumPathEnrollment, enrollment),
            )
            if item is not None
        ]
        if not matches:
            raise ResourceNotFoundError("Enrollment", enrollment)
        if len(matches) > 1:
            raise ResourceValidationError(
                "enrollment_type is required when IDs overlap"
            )
        return matches[0]
    if enrollment_type is not None:
        raise ResourceValidationError(
            "enrollment_type is only used with an integer enrollment ID"
        )
    return enrollment


def list_learner_course_enrollments(
    db: Session,
    learner_id: int,
) -> list[CourseEnrollment]:
    _get(db, Learner, learner_id)
    return list(
        db.scalars(
            select(CourseEnrollment)
            .where(CourseEnrollment.learner_id == learner_id)
            .options(selectinload(CourseEnrollment.course))
            .order_by(CourseEnrollment.enrolled_at, CourseEnrollment.id)
        )
    )


def list_learner_path_enrollments(
    db: Session,
    learner_id: int,
) -> list[CurriculumPathEnrollment]:
    _get(db, Learner, learner_id)
    return list(
        db.scalars(
            select(CurriculumPathEnrollment)
            .where(CurriculumPathEnrollment.learner_id == learner_id)
            .options(
                selectinload(CurriculumPathEnrollment.curriculum_path)
            )
            .order_by(
                CurriculumPathEnrollment.enrolled_at,
                CurriculumPathEnrollment.id,
            )
        )
    )


def list_learner_enrollments(
    db: Session,
    learner_id: int,
) -> list[CourseEnrollment | CurriculumPathEnrollment]:
    records: list[CourseEnrollment | CurriculumPathEnrollment] = [
        *list_learner_course_enrollments(db, learner_id),
        *list_learner_path_enrollments(db, learner_id),
    ]
    return sorted(records, key=lambda item: (item.enrolled_at, item.id))


def _get_or_create_progress(
    db: Session,
    learner_id: int,
    lesson_id: int,
) -> tuple[LessonProgress, bool]:
    _get(db, Learner, learner_id)
    _get(db, Lesson, lesson_id)
    progress = db.scalar(
        select(LessonProgress).where(
            LessonProgress.learner_id == learner_id,
            LessonProgress.lesson_id == lesson_id,
        )
    )
    if progress is not None:
        return progress, False
    progress = LessonProgress(
        learner_id=learner_id,
        lesson_id=lesson_id,
    )
    db.add(progress)
    db.flush()
    return progress, True


def get_or_create_lesson_progress(
    db: Session,
    learner_id: int,
    lesson_id: int,
    *,
    commit: bool = True,
) -> LessonProgress:
    progress, created = _get_or_create_progress(db, learner_id, lesson_id)
    if created:
        _finalize(
            db,
            commit=commit,
            conflict_message="Lesson progress already exists",
        )
    return progress


def _touch_related_enrollments(
    db: Session,
    learner_id: int,
    lesson_id: int,
    when: datetime,
) -> None:
    course_id = db.scalar(
        select(Module.course_id)
        .join(Lesson, Lesson.module_id == Module.id)
        .where(Lesson.id == lesson_id)
    )
    if course_id is not None:
        enrollment = db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.learner_id == learner_id,
                CourseEnrollment.course_id == course_id,
            )
        )
        if enrollment is not None:
            enrollment.last_accessed_at = when
    path_ids = list(
        db.scalars(
            select(CurriculumPathLesson.curriculum_path_id).where(
                CurriculumPathLesson.lesson_id == lesson_id
            )
        )
    )
    if path_ids:
        for enrollment in db.scalars(
            select(CurriculumPathEnrollment).where(
                CurriculumPathEnrollment.learner_id == learner_id,
                CurriculumPathEnrollment.curriculum_path_id.in_(path_ids),
            )
        ):
            enrollment.last_accessed_at = when


def start_lesson(
    db: Session,
    learner_id: int,
    lesson_id: int,
    *,
    commit: bool = True,
) -> LessonProgress:
    progress, _ = _get_or_create_progress(db, learner_id, lesson_id)
    now = utc_now()
    if progress.status == LessonProgressStatus.NOT_STARTED.value:
        progress.status = LessonProgressStatus.IN_PROGRESS.value
        progress.started_at = now
        progress.attempt_count += 1
    progress.last_accessed_at = now
    _touch_related_enrollments(db, learner_id, lesson_id, now)
    _finalize(
        db,
        commit=commit,
        conflict_message="Lesson could not be started",
    )
    return progress


def record_lesson_access(
    db: Session,
    learner_id: int,
    lesson_id: int,
    *,
    accessed_at: datetime | None = None,
    commit: bool = True,
) -> LessonProgress:
    progress, _ = _get_or_create_progress(db, learner_id, lesson_id)
    when = accessed_at or utc_now()
    progress.last_accessed_at = when
    _touch_related_enrollments(db, learner_id, lesson_id, when)
    _finalize(
        db,
        commit=commit,
        conflict_message="Lesson access could not be recorded",
    )
    return progress


def add_lesson_time(
    db: Session,
    learner_id: int,
    lesson_id: int,
    seconds: int,
    *,
    commit: bool = True,
) -> LessonProgress:
    if seconds < 0:
        raise ResourceValidationError("time spent cannot be negative")
    progress, _ = _get_or_create_progress(db, learner_id, lesson_id)
    progress.time_spent_seconds += seconds
    progress.last_accessed_at = utc_now()
    _touch_related_enrollments(
        db, learner_id, lesson_id, progress.last_accessed_at
    )
    _finalize(
        db,
        commit=commit,
        conflict_message="Lesson time could not be recorded",
    )
    return progress


def complete_lesson(
    db: Session,
    learner_id: int,
    lesson_id: int,
    *,
    completion_source: CompletionSource | str = CompletionSource.MANUAL,
    metadata_json: dict[str, Any] | list[Any] | None = None,
    completed_at: datetime | None = None,
    commit: bool = True,
) -> LessonProgress:
    source = _enum_value(
        "completion_source", completion_source, CompletionSource
    )
    _validate_json(metadata_json, "metadata_json")
    progress, _ = _get_or_create_progress(db, learner_id, lesson_id)
    if progress.status == LessonProgressStatus.COMPLETED.value:
        return progress
    now = completed_at or utc_now()
    progress.status = LessonProgressStatus.COMPLETED.value
    progress.progress_percent = 100.0
    progress.started_at = progress.started_at or now
    progress.completed_at = now
    progress.last_accessed_at = now
    if progress.attempt_count == 0:
        progress.attempt_count = 1
    completion = LessonCompletion(
        learner_id=learner_id,
        lesson_id=lesson_id,
        completed_at=now,
        completion_source=source,
        metadata_json=metadata_json,
    )
    db.add(completion)
    db.flush()
    _recalculate_related_enrollments(
        db, learner_id, lesson_id, now=now
    )
    _finalize(
        db,
        commit=commit,
        conflict_message="Lesson completion could not be recorded",
    )
    return progress


def update_lesson_progress(
    db: Session,
    learner_id: int,
    lesson_id: int,
    progress_percent: float,
    *,
    commit: bool = True,
) -> LessonProgress:
    _validate_percentage(progress_percent)
    if progress_percent == 100:
        return complete_lesson(
            db,
            learner_id,
            lesson_id,
            completion_source=CompletionSource.PROGRESS,
            commit=commit,
        )
    progress, _ = _get_or_create_progress(db, learner_id, lesson_id)
    if progress.status == LessonProgressStatus.COMPLETED.value:
        raise ResourceValidationError(
            "Completed lesson must be explicitly reset before reopening"
        )
    now = utc_now()
    progress.progress_percent = _percentage(progress_percent)
    if progress.status == LessonProgressStatus.NOT_STARTED.value:
        progress.status = LessonProgressStatus.IN_PROGRESS.value
        progress.started_at = now
        progress.attempt_count += 1
    progress.last_accessed_at = now
    _touch_related_enrollments(db, learner_id, lesson_id, now)
    _finalize(
        db,
        commit=commit,
        conflict_message="Lesson progress could not be updated",
    )
    return progress


def reset_lesson_progress(
    db: Session,
    learner_id: int,
    lesson_id: int,
    *,
    explicit: bool = False,
    explicit_reset: bool | None = None,
    allow_reset: bool | None = None,
    confirm: bool | None = None,
    commit: bool = True,
) -> LessonProgress:
    confirmed = (
        explicit
        or explicit_reset is True
        or allow_reset is True
        or confirm is True
    )
    if not confirmed:
        raise ResourceValidationError(
            "Lesson reset requires an explicit confirmation flag"
        )
    progress, _ = _get_or_create_progress(db, learner_id, lesson_id)
    now = utc_now()
    progress.status = LessonProgressStatus.NOT_STARTED.value
    progress.progress_percent = 0.0
    progress.started_at = None
    progress.completed_at = None
    progress.last_accessed_at = now
    _recalculate_related_enrollments(
        db, learner_id, lesson_id, now=now
    )
    _finalize(
        db,
        commit=commit,
        conflict_message="Lesson progress could not be reset",
    )
    return progress


def list_learner_lesson_progress(
    db: Session,
    learner_id: int,
) -> list[LessonProgress]:
    _get(db, Learner, learner_id)
    return list(
        db.scalars(
            select(LessonProgress)
            .where(LessonProgress.learner_id == learner_id)
            .options(selectinload(LessonProgress.lesson))
            .order_by(
                LessonProgress.last_accessed_at.desc(),
                LessonProgress.id,
            )
        )
    )


def list_lesson_completions(
    db: Session,
    learner_id: int,
    *,
    lesson_id: int | None = None,
) -> list[LessonCompletion]:
    _get(db, Learner, learner_id)
    statement = select(LessonCompletion).where(
        LessonCompletion.learner_id == learner_id
    )
    if lesson_id is not None:
        _get(db, Lesson, lesson_id)
        statement = statement.where(
            LessonCompletion.lesson_id == lesson_id
        )
    return list(
        db.scalars(
            statement.order_by(
                LessonCompletion.completed_at,
                LessonCompletion.id,
            )
        )
    )


def _validate_assessment_owner(
    db: Session,
    data: Mapping[str, Any],
) -> None:
    owners = {
        "lesson_id": Lesson,
        "module_id": Module,
        "course_id": Course,
    }
    selected = [
        (field, value)
        for field, value in data.items()
        if field in owners and value is not None
    ]
    if len(selected) != 1:
        raise ResourceValidationError(
            "Assessment requires exactly one owner: "
            "lesson_id, module_id, or course_id"
        )
    field, owner_id = selected[0]
    _get(db, owners[field], owner_id)


def _validated_option_data(
    value: Mapping[str, Any] | Any,
    display_order: int,
) -> dict[str, Any]:
    data = _data(value)
    option_text = str(data.get("option_text", "")).strip()
    if not option_text:
        raise ResourceValidationError("Assessment option requires option_text")
    order = data.get("display_order", display_order)
    if order < 0:
        raise ResourceValidationError(
            "Assessment option display_order must be non-negative"
        )
    return {
        "option_text": option_text,
        "is_correct": bool(data.get("is_correct", False)),
        "display_order": order,
    }


def _validated_question_data(
    value: Mapping[str, Any] | Any,
    display_order: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = _data(value)
    question_type = _enum_value(
        "question_type", data.get("question_type"), QuestionType
    )
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        raise ResourceValidationError("Assessment question requires prompt")
    points = float(data.get("points", 1.0))
    order = data.get("display_order", display_order)
    if points < 0:
        raise ResourceValidationError("Question points cannot be negative")
    if order < 0:
        raise ResourceValidationError(
            "Question display_order must be non-negative"
        )
    metadata_json = data.get("metadata_json")
    _validate_json(metadata_json, "metadata_json")
    option_values = data.get("options", [])
    options = [
        _validated_option_data(option, position)
        for position, option in enumerate(option_values)
    ]
    if question_type == QuestionType.SHORT_ANSWER.value:
        if options:
            raise ResourceValidationError(
                "Short-answer questions cannot contain options"
            )
    else:
        if len(options) < 2:
            raise ResourceValidationError(
                "Choice questions require at least two options"
            )
        if question_type == QuestionType.TRUE_FALSE.value and len(options) != 2:
            raise ResourceValidationError(
                "True/false questions require exactly two options"
            )
        if sum(option["is_correct"] for option in options) != 1:
            raise ResourceValidationError(
                "Choice questions require exactly one correct option"
            )
    question_data = {
        "question_type": question_type,
        "prompt": prompt,
        "explanation": data.get("explanation"),
        "points": points,
        "display_order": order,
        "metadata_json": metadata_json,
    }
    return question_data, options


def create_assessment(
    db: Session,
    values: Mapping[str, Any] | Any,
    *,
    commit: bool = True,
) -> Assessment:
    data = _data(values)
    questions = data.pop("questions", [])
    _validate_assessment_owner(db, data)
    title = str(data.get("title", "")).strip()
    if not title:
        raise ResourceValidationError("Assessment requires title")
    slug = normalize_slug(data.get("slug") or title)
    if db.scalar(
        select(Assessment.id).where(Assessment.slug == slug)
    ) is not None:
        raise ResourceConflictError("Assessment slug already exists")
    assessment_type = _enum_value(
        "assessment_type",
        data.get("assessment_type", AssessmentType.QUIZ.value),
        AssessmentType,
    )
    passing_score = float(data.get("passing_score", 70.0))
    _validate_percentage(passing_score, "passing_score")
    max_attempts = data.get("max_attempts")
    time_limit = data.get("time_limit_minutes")
    display_order = data.get("display_order", 0)
    if max_attempts is not None and max_attempts < 1:
        raise ResourceValidationError("max_attempts must be positive")
    if time_limit is not None and time_limit < 1:
        raise ResourceValidationError("time_limit_minutes must be positive")
    if display_order < 0:
        raise ResourceValidationError(
            "display_order must be non-negative"
        )
    validated_questions = [
        _validated_question_data(question, position)
        for position, question in enumerate(questions)
    ]
    try:
        assessment = Assessment(
            lesson_id=data.get("lesson_id"),
            module_id=data.get("module_id"),
            course_id=data.get("course_id"),
            title=title,
            slug=slug,
            description=data.get("description"),
            assessment_type=assessment_type,
            passing_score=passing_score,
            max_attempts=max_attempts,
            time_limit_minutes=time_limit,
            is_active=bool(data.get("is_active", True)),
            display_order=display_order,
        )
        db.add(assessment)
        db.flush()
        for question_data, option_data in validated_questions:
            question = AssessmentQuestion(
                assessment_id=assessment.id,
                **question_data,
            )
            db.add(question)
            db.flush()
            db.add_all(
                AssessmentOption(question_id=question.id, **option)
                for option in option_data
            )
        _finalize(
            db,
            commit=commit,
            conflict_message="Assessment could not be created",
        )
    except Exception:
        db.rollback()
        raise
    return get_assessment(db, assessment.id)


def get_assessment(db: Session, assessment_id: int) -> Assessment:
    assessment = db.scalar(
        select(Assessment)
        .where(Assessment.id == assessment_id)
        .options(
            selectinload(Assessment.questions).selectinload(
                AssessmentQuestion.options
            )
        )
        .execution_options(populate_existing=True)
    )
    if assessment is None:
        raise ResourceNotFoundError("Assessment", assessment_id)
    return assessment


def list_assessments(
    db: Session,
    *,
    lesson_id: int | None = None,
    module_id: int | None = None,
    course_id: int | None = None,
    active_only: bool = False,
) -> list[Assessment]:
    statement = select(Assessment).options(
        selectinload(Assessment.questions).selectinload(
            AssessmentQuestion.options
        )
    )
    if lesson_id is not None:
        statement = statement.where(Assessment.lesson_id == lesson_id)
    if module_id is not None:
        statement = statement.where(Assessment.module_id == module_id)
    if course_id is not None:
        statement = statement.where(Assessment.course_id == course_id)
    if active_only:
        statement = statement.where(Assessment.is_active.is_(True))
    return list(
        db.scalars(
            statement.order_by(Assessment.display_order, Assessment.id)
        )
    )


def start_assessment_attempt(
    db: Session,
    learner_id: int,
    assessment_id: int,
    *,
    commit: bool = True,
) -> AssessmentAttempt:
    _require_active_learner(db, learner_id)
    assessment = _get(db, Assessment, assessment_id)
    if not assessment.is_active:
        raise ResourceValidationError("Assessment is not active")
    attempt_count, maximum_number = db.execute(
        select(
            func.count(AssessmentAttempt.id),
            func.max(AssessmentAttempt.attempt_number),
        ).where(
            AssessmentAttempt.learner_id == learner_id,
            AssessmentAttempt.assessment_id == assessment_id,
        )
    ).one()
    if (
        assessment.max_attempts is not None
        and int(attempt_count or 0) >= assessment.max_attempts
    ):
        raise ResourceConflictError("Assessment attempt limit reached")
    attempt = AssessmentAttempt(
        learner_id=learner_id,
        assessment_id=assessment_id,
        attempt_number=int(maximum_number or 0) + 1,
        status=AttemptStatus.IN_PROGRESS.value,
    )
    db.add(attempt)
    _finalize(
        db,
        commit=commit,
        conflict_message="Assessment attempt could not be started",
    )
    return attempt


def _answer_data(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    data = _data(value)
    question_id = data.get("question_id")
    if question_id is None:
        raise ResourceValidationError("Answer requires question_id")
    return {
        "question_id": question_id,
        "selected_option_id": data.get("selected_option_id"),
        "text_answer": data.get("text_answer"),
    }


def submit_assessment_attempt(
    db: Session,
    attempt_id: int,
    answers: Sequence[Mapping[str, Any] | Any],
    *,
    time_spent_seconds: int = 0,
    commit: bool = True,
) -> AssessmentAttempt:
    if time_spent_seconds < 0:
        raise ResourceValidationError("time spent cannot be negative")
    attempt = db.scalar(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.id == attempt_id)
        .options(
            selectinload(AssessmentAttempt.assessment)
            .selectinload(Assessment.questions)
            .selectinload(AssessmentQuestion.options),
            selectinload(AssessmentAttempt.answers),
        )
    )
    if attempt is None:
        raise ResourceNotFoundError("AssessmentAttempt", attempt_id)
    if attempt.status == AttemptStatus.SUBMITTED.value:
        raise ResourceConflictError(
            "Submitted assessment attempt cannot be resubmitted"
        )
    if attempt.answers:
        raise ResourceConflictError("Assessment attempt already has answers")
    answer_values = [_answer_data(answer) for answer in answers]
    question_ids = [answer["question_id"] for answer in answer_values]
    if len(question_ids) != len(set(question_ids)):
        raise ResourceConflictError(
            "Assessment submission contains duplicate answers"
        )
    questions = {
        question.id: question for question in attempt.assessment.questions
    }
    unknown = sorted(set(question_ids) - set(questions))
    if unknown:
        raise ResourceValidationError(
            "Question does not belong to assessment: "
            + ", ".join(str(item) for item in unknown)
        )
    points_earned = 0.0
    graded_question_ids: set[int] = set()
    try:
        for answer_data in answer_values:
            question = questions[answer_data["question_id"]]
            selected_option_id = answer_data["selected_option_id"]
            text_answer = answer_data["text_answer"]
            is_correct: bool | None = None
            points_awarded: float | None = None
            answer_grading_status = GradingStatus.MANUAL_GRADING_REQUIRED.value
            if question.question_type in {
                QuestionType.MULTIPLE_CHOICE.value,
                QuestionType.TRUE_FALSE.value,
            }:
                if selected_option_id is None:
                    raise ResourceValidationError(
                        "Choice answers require selected_option_id"
                    )
                option = next(
                    (
                        item
                        for item in question.options
                        if item.id == selected_option_id
                    ),
                    None,
                )
                if option is None:
                    raise ResourceValidationError(
                        "Selected option does not belong to question"
                    )
                is_correct = option.is_correct
                points_awarded = question.points if is_correct else 0.0
                points_earned += points_awarded
                graded_question_ids.add(question.id)
                answer_grading_status = (
                    GradingStatus.AUTOMATIC_GRADED.value
                )
            else:
                if selected_option_id is not None:
                    raise ResourceValidationError(
                        "Short-answer responses cannot select an option"
                    )
                if text_answer is not None:
                    text_answer = str(text_answer).strip() or None
            db.add(
                AssessmentAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    selected_option_id=selected_option_id,
                    text_answer=text_answer,
                    is_correct=is_correct,
                    points_awarded=points_awarded,
                    grading_status=answer_grading_status,
                )
            )
        points_possible = sum(
            question.points for question in questions.values()
        )
        attempt.points_earned = round(points_earned, 4)
        attempt.points_possible = round(points_possible, 4)
        attempt.score_percent = _percentage(
            points_earned * 100.0 / points_possible
            if points_possible > 0
            else 0.0
        )
        attempt.automatic_points_earned = attempt.points_earned
        attempt.automatic_score_percent = attempt.score_percent
        grading_complete = (
            set(question_ids) == set(questions)
            and graded_question_ids == set(questions)
        )
        attempt.passed = (
            attempt.score_percent >= attempt.assessment.passing_score
            if grading_complete
            else None
        )
        if grading_complete:
            attempt.final_score_percent = attempt.score_percent
            attempt.final_passed = attempt.passed
            attempt.grading_status = GradingStatus.FINAL.value
        else:
            attempt.final_score_percent = None
            attempt.final_passed = None
            attempt.grading_status = (
                GradingStatus.MANUAL_GRADING_REQUIRED.value
                if any(
                    question.question_type
                    == QuestionType.SHORT_ANSWER.value
                    for question in questions.values()
                )
                else GradingStatus.PENDING.value
            )
        attempt.status = AttemptStatus.SUBMITTED.value
        attempt.submitted_at = utc_now()
        attempt.time_spent_seconds = time_spent_seconds
        _finalize(
            db,
            commit=commit,
            conflict_message="Assessment answers could not be submitted",
        )
    except Exception:
        db.rollback()
        raise
    return get_assessment_attempt(db, attempt.id)


def get_assessment_attempt(
    db: Session,
    attempt_id: int,
) -> AssessmentAttempt:
    attempt = db.scalar(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.id == attempt_id)
        .options(
            selectinload(AssessmentAttempt.answers),
            selectinload(AssessmentAttempt.assessment),
        )
        .execution_options(populate_existing=True)
    )
    if attempt is None:
        raise ResourceNotFoundError("AssessmentAttempt", attempt_id)
    return attempt


def list_learner_attempts(
    db: Session,
    learner_id: int,
    *,
    assessment_id: int | None = None,
) -> list[AssessmentAttempt]:
    _get(db, Learner, learner_id)
    statement = (
        select(AssessmentAttempt)
        .where(AssessmentAttempt.learner_id == learner_id)
        .options(
            selectinload(AssessmentAttempt.answers),
            selectinload(AssessmentAttempt.assessment),
        )
    )
    if assessment_id is not None:
        _get(db, Assessment, assessment_id)
        statement = statement.where(
            AssessmentAttempt.assessment_id == assessment_id
        )
    return list(
        db.scalars(
            statement.order_by(
                AssessmentAttempt.started_at,
                AssessmentAttempt.attempt_number,
            )
        )
    )


def get_course_progress_summary(
    db: Session,
    learner_id: int,
    course_id: int,
) -> CourseProgressSummary:
    _get(db, Learner, learner_id)
    lesson_ids = _course_lesson_ids(db, course_id)
    total, completed, time_spent, last_accessed = _progress_aggregate(
        db, learner_id, lesson_ids
    )
    enrollment = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.learner_id == learner_id,
            CourseEnrollment.course_id == course_id,
        )
    )
    return CourseProgressSummary(
        learner_id=learner_id,
        course_id=course_id,
        enrollment_id=enrollment.id if enrollment is not None else None,
        status=enrollment.status if enrollment is not None else None,
        progress_percent=_completion_percentage(total, completed),
        total_lessons=total,
        completed_lessons=completed,
        time_spent_seconds=time_spent,
        started_at=enrollment.started_at if enrollment is not None else None,
        completed_at=(
            enrollment.completed_at if enrollment is not None else None
        ),
        last_accessed_at=(
            enrollment.last_accessed_at
            if enrollment is not None
            else last_accessed
        ),
    )


def get_path_progress_summary(
    db: Session,
    learner_id: int,
    curriculum_path_id: int,
) -> PathProgressSummary:
    _get(db, Learner, learner_id)
    lesson_ids = _path_lesson_ids(db, curriculum_path_id)
    total, completed, time_spent, last_accessed = _progress_aggregate(
        db, learner_id, lesson_ids
    )
    enrollment = db.scalar(
        select(CurriculumPathEnrollment).where(
            CurriculumPathEnrollment.learner_id == learner_id,
            CurriculumPathEnrollment.curriculum_path_id
            == curriculum_path_id,
        )
    )
    return PathProgressSummary(
        learner_id=learner_id,
        curriculum_path_id=curriculum_path_id,
        enrollment_id=enrollment.id if enrollment is not None else None,
        status=enrollment.status if enrollment is not None else None,
        progress_percent=_completion_percentage(total, completed),
        total_lessons=total,
        completed_lessons=completed,
        time_spent_seconds=time_spent,
        started_at=enrollment.started_at if enrollment is not None else None,
        completed_at=(
            enrollment.completed_at if enrollment is not None else None
        ),
        last_accessed_at=(
            enrollment.last_accessed_at
            if enrollment is not None
            else last_accessed
        ),
    )


def _recent_activity(
    db: Session,
    learner_id: int,
    *,
    limit: int,
) -> list[RecentActivityItem]:
    items: list[RecentActivityItem] = []
    completions = db.scalars(
        select(LessonCompletion)
        .where(LessonCompletion.learner_id == learner_id)
        .order_by(
            LessonCompletion.completed_at.desc(),
            LessonCompletion.id.desc(),
        )
        .limit(limit)
    )
    items.extend(
        RecentActivityItem(
            activity_type="lesson_completed",
            occurred_at=item.completed_at,
            lesson_id=item.lesson_id,
            detail=item.completion_source,
        )
        for item in completions
    )
    attempts = db.scalars(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.learner_id == learner_id)
        .order_by(
            AssessmentAttempt.started_at.desc(),
            AssessmentAttempt.id.desc(),
        )
        .limit(limit)
    )
    items.extend(
        RecentActivityItem(
            activity_type=(
                "assessment_submitted"
                if item.submitted_at is not None
                else "assessment_started"
            ),
            occurred_at=item.submitted_at or item.started_at,
            assessment_id=item.assessment_id,
            detail=item.status,
        )
        for item in attempts
    )
    items.sort(key=lambda item: item.occurred_at, reverse=True)
    return items[:limit]


def get_learner_progress_summary(
    db: Session,
    learner_id: int,
    *,
    recent_limit: int = 10,
) -> LearnerProgressSummary:
    learner = get_learner(db, learner_id)
    course_enrollments = list_learner_course_enrollments(db, learner_id)
    path_enrollments = list_learner_path_enrollments(db, learner_id)
    course_progress = [
        get_course_progress_summary(db, learner_id, item.course_id)
        for item in course_enrollments
    ]
    path_progress = [
        get_path_progress_summary(
            db, learner_id, item.curriculum_path_id
        )
        for item in path_enrollments
    ]
    progress_values = [
        item.progress_percent
        for item in [*course_progress, *path_progress]
    ]
    overall = (
        _percentage(sum(progress_values) / len(progress_values))
        if progress_values
        else 0.0
    )
    (
        attempts_started,
        attempts_submitted,
        attempts_passed,
        average_score,
    ) = db.execute(
        select(
            func.count(AssessmentAttempt.id),
            func.count(AssessmentAttempt.submitted_at),
            func.coalesce(
                func.sum(
                    case(
                        (AssessmentAttempt.passed.is_(True), 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.avg(AssessmentAttempt.score_percent),
        ).where(AssessmentAttempt.learner_id == learner_id)
    ).one()
    completed_lessons = db.scalar(
        select(func.count(LessonProgress.id)).where(
            LessonProgress.learner_id == learner_id,
            LessonProgress.status == LessonProgressStatus.COMPLETED.value,
        )
    )
    completion_events = db.scalar(
        select(func.count(LessonCompletion.id)).where(
            LessonCompletion.learner_id == learner_id
        )
    )
    total_time = db.scalar(
        select(
            func.coalesce(func.sum(LessonProgress.time_spent_seconds), 0)
        ).where(LessonProgress.learner_id == learner_id)
    )
    return LearnerProgressSummary(
        learner=LearnerRead.model_validate(learner),
        overall_progress_percent=overall,
        course_enrollment_count=len(course_enrollments),
        path_enrollment_count=len(path_enrollments),
        completed_course_count=sum(
            item.status == EnrollmentStatus.COMPLETED.value
            for item in course_enrollments
        ),
        completed_path_count=sum(
            item.status == EnrollmentStatus.COMPLETED.value
            for item in path_enrollments
        ),
        completed_lesson_count=int(completed_lessons or 0),
        completion_event_count=int(completion_events or 0),
        total_time_spent_seconds=int(total_time or 0),
        course_progress=course_progress,
        path_progress=path_progress,
        recent_activity=_recent_activity(
            db, learner_id, limit=max(recent_limit, 0)
        ),
        assessment_statistics=AssessmentStatistics(
            attempts_started=int(attempts_started or 0),
            attempts_submitted=int(attempts_submitted or 0),
            attempts_passed=int(attempts_passed or 0),
            average_score_percent=(
                _percentage(average_score)
                if average_score is not None
                else None
            ),
        ),
    )


enroll_course = enroll_in_course
enroll_path = enroll_in_curriculum_path
enroll_curriculum_path = enroll_in_curriculum_path
list_learner_curriculum_path_enrollments = list_learner_path_enrollments
record_access = record_lesson_access
calculate_course_progress = calculate_course_completion
calculate_curriculum_path_completion = calculate_path_completion
course_progress_summary = get_course_progress_summary
path_progress_summary = get_path_progress_summary
learner_progress_summary = get_learner_progress_summary
start_attempt = start_assessment_attempt
submit_attempt = submit_assessment_attempt
get_or_create_progress = get_or_create_lesson_progress
list_lesson_progress = list_learner_lesson_progress
list_enrollments = list_learner_enrollments
list_attempts = list_learner_attempts
get_curriculum_path_progress_summary = get_path_progress_summary
update_progress = update_lesson_progress
submit_answers = submit_assessment_attempt


def add_time_spent(
    db: Session,
    learner_id: int,
    lesson_id: int,
    seconds: int | None = None,
    *,
    time_spent_seconds: int | None = None,
    commit: bool = True,
) -> LessonProgress:
    if seconds is not None and time_spent_seconds is not None:
        raise ResourceValidationError(
            "provide seconds or time_spent_seconds, not both"
        )
    duration = (
        seconds if seconds is not None else time_spent_seconds
    )
    if duration is None:
        raise ResourceValidationError("time spent is required")
    return add_lesson_time(
        db,
        learner_id,
        lesson_id,
        duration,
        commit=commit,
    )


__all__ = [
    "PERCENTAGE_DECIMALS",
    "add_lesson_time",
    "add_time_spent",
    "calculate_course_completion",
    "calculate_course_progress",
    "calculate_curriculum_path_completion",
    "calculate_path_completion",
    "complete_course_enrollment",
    "complete_curriculum_path_enrollment",
    "complete_enrollment",
    "complete_lesson",
    "course_progress_summary",
    "create_assessment",
    "create_learner",
    "deactivate_learner",
    "enroll_course",
    "enroll_curriculum_path",
    "enroll_in_course",
    "enroll_in_curriculum_path",
    "enroll_path",
    "get_assessment",
    "get_assessment_attempt",
    "get_course_progress_summary",
    "get_curriculum_path_progress_summary",
    "get_learner",
    "get_learner_progress_summary",
    "get_or_create_lesson_progress",
    "get_or_create_progress",
    "get_path_progress_summary",
    "learner_progress_summary",
    "list_assessments",
    "list_attempts",
    "list_enrollments",
    "list_learner_attempts",
    "list_learner_course_enrollments",
    "list_learner_curriculum_path_enrollments",
    "list_learner_enrollments",
    "list_learner_lesson_progress",
    "list_learner_path_enrollments",
    "list_lesson_completions",
    "list_lesson_progress",
    "path_progress_summary",
    "record_access",
    "record_lesson_access",
    "reset_lesson_progress",
    "start_assessment_attempt",
    "start_attempt",
    "start_course_enrollment",
    "start_curriculum_path_enrollment",
    "start_enrollment",
    "start_lesson",
    "submit_assessment_attempt",
    "submit_answers",
    "submit_attempt",
    "update_learner",
    "update_lesson_progress",
    "update_progress",
]
