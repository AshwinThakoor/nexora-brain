from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AssessmentAttempt,
    AttemptStatus,
    Course,
    CourseEnrollment,
    CurriculumPathEnrollment,
    Degree,
    KnowledgeLifecycleStatus,
    Lesson,
    Module,
    School,
)
from ..schemas.api_curriculum import AcademyPage
from ..schemas.api_learning import (
    AttemptResultSummary,
    CourseEnrollmentRequest,
    CourseEnrollmentResponse,
    LearnerAssessmentDetail,
    LearnerAttemptDetail,
    LearnerDashboardResponse,
    LearnerProfileResponse,
    LessonProgressRequest,
    LessonProgressResponse,
    PathEnrollmentRequest,
    PathEnrollmentResponse,
    StartAttemptResponse,
    SubmitAttemptRequest,
)
from ..services import learning
from ..services.authorization import (
    Principal,
    require_owned_learner_id,
    resolve_learner,
)
from ..services.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
)
from .dependencies import get_current_principal, get_db


router = APIRouter(prefix="/api/v1/academy", tags=["academy-learning"])


def _page(items: list, *, offset: int, limit: int) -> dict:
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "skip": offset,
    }


def _attempt_payload(attempt: AssessmentAttempt) -> dict:
    return {
        "id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "grading_status": attempt.grading_status,
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
        "score_percent": attempt.score_percent,
        "points_earned": attempt.points_earned,
        "points_possible": attempt.points_possible,
        "passed": attempt.passed,
        "automatic_score_percent": attempt.automatic_score_percent,
        "automatic_points_earned": attempt.automatic_points_earned,
        "final_score_percent": attempt.final_score_percent,
        "final_passed": attempt.final_passed,
        "answers": [
            {
                "id": answer.id,
                "question_id": answer.question_id,
                "selected_option_id": answer.selected_option_id,
                "text_answer": answer.text_answer,
                "grading_status": answer.grading_status,
                "is_correct": answer.is_correct,
                "points_awarded": answer.points_awarded,
                "manual_points_awarded": (
                    answer.current_manual_grade.points_awarded
                    if answer.current_manual_grade is not None
                    else None
                ),
                "manual_is_correct": (
                    answer.current_manual_grade.is_correct
                    if answer.current_manual_grade is not None
                    else None
                ),
                "feedback": (
                    answer.current_manual_grade.feedback
                    if answer.current_manual_grade is not None
                    else None
                ),
            }
            for answer in attempt.answers
        ],
    }


def _own_attempt(
    db: Session,
    principal: Principal,
    attempt_id: int,
) -> AssessmentAttempt:
    attempt = learning.get_assessment_attempt(db, attempt_id)
    require_owned_learner_id(db, principal, attempt.learner_id)
    return attempt


def _require_visible_assessment(db: Session, assessment) -> None:
    if not assessment.is_active:
        raise ResourceNotFoundError("Assessment", assessment.id)
    if assessment.lesson_id is not None:
        _require_published_lesson(db, assessment.lesson_id)
    elif assessment.module_id is not None:
        module = db.get(Module, assessment.module_id)
        if module is None:
            raise ResourceNotFoundError("Assessment", assessment.id)
        _require_visible_course(db, module.course_id)
    elif assessment.course_id is not None:
        _require_visible_course(db, assessment.course_id)


def _require_published_lesson(db: Session, lesson_id: int) -> Lesson:
    lesson = db.scalar(
        select(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(
            Lesson.id == lesson_id,
            Lesson.status == KnowledgeLifecycleStatus.PUBLISHED.value,
            School.is_active.is_(True),
        )
    )
    if lesson is None:
        raise ResourceNotFoundError("Lesson", lesson_id)
    return lesson


def _require_visible_course(db: Session, course_id: int) -> Course:
    course = db.scalar(
        select(Course)
        .join(Degree, Degree.id == Course.degree_id)
        .join(School, School.id == Degree.school_id)
        .where(Course.id == course_id, School.is_active.is_(True))
    )
    if course is None:
        raise ResourceNotFoundError("Course", course_id)
    return course


@router.get("/learners/me", response_model=LearnerProfileResponse)
def get_me(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return resolve_learner(db, principal)


@router.get(
    "/learners/me/dashboard",
    response_model=LearnerDashboardResponse,
)
def get_dashboard(
    recent_limit: int = Query(default=10, ge=0, le=50),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    return learning.get_learner_progress_summary(
        db, learner.id, recent_limit=recent_limit
    )


@router.post(
    "/enrollments/courses",
    response_model=CourseEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def enroll_course(
    request: CourseEnrollmentRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    _require_visible_course(db, request.course_id)
    return learning.enroll_in_course(db, learner.id, request.course_id)


@router.post(
    "/enrollments/paths",
    response_model=PathEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def enroll_path(
    request: PathEnrollmentRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    return learning.enroll_in_curriculum_path(
        db, learner.id, request.curriculum_path_id
    )


@router.get(
    "/enrollments/courses",
    response_model=AcademyPage[CourseEnrollmentResponse],
)
def list_course_enrollments(
    enrollment_status: str | None = Query(
        default=None,
        alias="status",
        max_length=50,
    ),
    course_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    items = learning.list_learner_course_enrollments(db, learner.id)
    if enrollment_status is not None:
        items = [
            item for item in items if item.status == enrollment_status
        ]
    if course_id is not None:
        items = [item for item in items if item.course_id == course_id]
    return _page(items, offset=offset, limit=limit)


@router.get(
    "/enrollments/paths",
    response_model=AcademyPage[PathEnrollmentResponse],
)
def list_path_enrollments(
    enrollment_status: str | None = Query(
        default=None,
        alias="status",
        max_length=50,
    ),
    curriculum_path_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    items = learning.list_learner_path_enrollments(db, learner.id)
    if enrollment_status is not None:
        items = [
            item for item in items if item.status == enrollment_status
        ]
    if curriculum_path_id is not None:
        items = [
            item
            for item in items
            if item.curriculum_path_id == curriculum_path_id
        ]
    return _page(items, offset=offset, limit=limit)


@router.get(
    "/enrollments/courses/{enrollment_id}",
    response_model=CourseEnrollmentResponse,
)
def get_course_enrollment(
    enrollment_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    enrollment = db.get(CourseEnrollment, enrollment_id)
    if enrollment is None:
        raise ResourceNotFoundError("CourseEnrollment", enrollment_id)
    require_owned_learner_id(db, principal, enrollment.learner_id)
    return enrollment


@router.get(
    "/enrollments/paths/{enrollment_id}",
    response_model=PathEnrollmentResponse,
)
def get_path_enrollment(
    enrollment_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    enrollment = db.get(CurriculumPathEnrollment, enrollment_id)
    if enrollment is None:
        raise ResourceNotFoundError(
            "CurriculumPathEnrollment", enrollment_id
        )
    require_owned_learner_id(db, principal, enrollment.learner_id)
    return enrollment


@router.post(
    "/progress/lessons/{lesson_id}/start",
    response_model=LessonProgressResponse,
)
def start_lesson(
    lesson_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    _require_published_lesson(db, lesson_id)
    return learning.start_lesson(db, learner.id, lesson_id)


@router.patch(
    "/progress/lessons/{lesson_id}",
    response_model=LessonProgressResponse,
)
def update_lesson(
    request: LessonProgressRequest,
    lesson_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    _require_published_lesson(db, lesson_id)
    if request.time_spent_seconds is not None:
        progress = learning.add_lesson_time(
            db,
            learner.id,
            lesson_id,
            request.time_spent_seconds,
            commit=request.progress_percent is None,
        )
    if request.progress_percent is not None:
        progress = learning.update_lesson_progress(
            db,
            learner.id,
            lesson_id,
            request.progress_percent,
        )
    return progress


@router.post(
    "/progress/lessons/{lesson_id}/complete",
    response_model=LessonProgressResponse,
)
def complete_lesson(
    lesson_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    _require_published_lesson(db, lesson_id)
    return learning.complete_lesson(db, learner.id, lesson_id)


@router.get(
    "/assessments/attempts",
    response_model=AcademyPage[LearnerAttemptDetail],
)
def list_attempts(
    assessment_id: int | None = Query(default=None, gt=0),
    attempt_status: str | None = Query(
        default=None,
        alias="status",
        max_length=50,
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    attempts = learning.list_learner_attempts(
        db, learner.id, assessment_id=assessment_id
    )
    if attempt_status is not None:
        attempts = [
            item for item in attempts if item.status == attempt_status
        ]
    attempts = list(reversed(attempts))
    payloads = [_attempt_payload(item) for item in attempts]
    return _page(payloads, offset=offset, limit=limit)


@router.get(
    "/assessments/attempts/{attempt_id}",
    response_model=LearnerAttemptDetail,
)
def get_attempt(
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return _attempt_payload(_own_attempt(db, principal, attempt_id))


@router.get(
    "/assessments/attempts/{attempt_id}/result",
    response_model=AttemptResultSummary,
)
def get_attempt_result(
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    attempt = _own_attempt(db, principal, attempt_id)
    if attempt.status != AttemptStatus.SUBMITTED.value:
        raise ResourceConflictError(
            "Assessment result is unavailable before submission"
        )
    return {
        "attempt_id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "grading_status": attempt.grading_status,
        "provisional_score_percent": attempt.score_percent,
        "provisional_passed": attempt.passed,
        "final_score_percent": attempt.final_score_percent,
        "final_passed": attempt.final_passed,
        "points_earned": attempt.points_earned,
        "points_possible": attempt.points_possible,
    }


@router.post(
    "/assessments/{assessment_id}/attempts",
    response_model=StartAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_attempt(
    assessment_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    learner = resolve_learner(db, principal)
    assessment = learning.get_assessment(db, assessment_id)
    _require_visible_assessment(db, assessment)
    return learning.start_assessment_attempt(
        db, learner.id, assessment_id
    )


@router.post(
    "/assessments/attempts/{attempt_id}/submit",
    response_model=LearnerAttemptDetail,
)
def submit_attempt(
    request: SubmitAttemptRequest,
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _own_attempt(db, principal, attempt_id)
    attempt = learning.submit_assessment_attempt(
        db,
        attempt_id,
        request.answers,
        time_spent_seconds=request.time_spent_seconds,
    )
    return _attempt_payload(attempt)


@router.get(
    "/assessments/{assessment_id}",
    response_model=LearnerAssessmentDetail,
)
def get_assessment(
    assessment_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    resolve_learner(db, principal)
    assessment = learning.get_assessment(db, assessment_id)
    _require_visible_assessment(db, assessment)
    return assessment


__all__ = ["router"]
