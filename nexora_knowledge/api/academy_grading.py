from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from ..schemas.api_curriculum import AcademyPage
from ..schemas.api_learning import LearnerAttemptDetail
from ..schemas.grading import (
    AssessmentReviewResponse,
    AttemptGradingSummary,
    ChangeGradeRequest,
    GradeShortAnswerRequest,
    GradingAuditEventResponse,
    GradingHistoryResponse,
    ManualGradeResponse,
    RegradeAttemptRequest,
    ReviewDecisionRequest,
    ReviewRequest,
)
from ..schemas.learning import CourseProgressSummary
from ..services import grading, learning
from ..services.authorization import Principal, require_course_scope
from .academy_learning import _attempt_payload
from .dependencies import get_current_principal, get_db


router = APIRouter(prefix="/api/v1/academy", tags=["academy-grading"])


def _page(
    items: list,
    *,
    total: int,
    offset: int,
    limit: int,
) -> dict:
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "skip": offset,
    }


@router.get(
    "/grading/learners/{learner_id}/courses/{course_id}/progress",
    response_model=CourseProgressSummary,
)
def learner_course_progress(
    learner_id: int = Path(gt=0),
    course_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    require_course_scope(principal, course_id)
    return learning.get_course_progress_summary(
        db, learner_id, course_id
    )


@router.get(
    "/grading/attempts",
    response_model=AcademyPage[AttemptGradingSummary],
)
def attempts_needing_grading(
    assessment_id: int | None = Query(default=None, gt=0),
    learner_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    items = grading.list_attempts_needing_grading(
        db,
        principal=principal,
        assessment_id=assessment_id,
        learner_id=learner_id,
        offset=offset,
        limit=limit,
    )
    total = grading.count_attempts_needing_grading(
        db,
        principal=principal,
        assessment_id=assessment_id,
        learner_id=learner_id,
    )
    return _page(items, total=total, offset=offset, limit=limit)


@router.get(
    "/grading/attempts/{attempt_id}",
    response_model=LearnerAttemptDetail,
)
def get_attempt_for_review(
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return _attempt_payload(
        grading.get_attempt_for_staff(
            db, attempt_id, principal=principal
        )
    )


@router.post(
    "/grading/answers/{answer_id}",
    response_model=ManualGradeResponse,
    status_code=status.HTTP_201_CREATED,
)
def grade_answer(
    request: GradeShortAnswerRequest,
    answer_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.grade_short_answer(
        db,
        answer_id,
        principal=principal,
        **request.model_dump(),
    )


@router.post(
    "/grading/answers/{answer_id}/changes",
    response_model=ManualGradeResponse,
    status_code=status.HTTP_201_CREATED,
)
def change_answer_grade(
    request: ChangeGradeRequest,
    answer_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.change_grade(
        db,
        answer_id,
        principal=principal,
        **request.model_dump(),
    )


@router.get(
    "/grading/answers/{answer_id}/history",
    response_model=GradingHistoryResponse,
)
def answer_grading_history(
    answer_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return {
        "grades": grading.list_manual_grades(
            db, answer_id, principal=principal
        ),
        "audit_events": grading.list_audit_events(
            db,
            principal=principal,
            answer_id=answer_id,
            limit=100,
        ),
    }


@router.get(
    "/grading/attempts/{attempt_id}/history",
    response_model=list[GradingAuditEventResponse],
)
def attempt_grading_history(
    attempt_id: int = Path(gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.list_audit_events(
        db,
        principal=principal,
        attempt_id=attempt_id,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/reviews/attempts/{attempt_id}/request",
    response_model=AssessmentReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_attempt_review(
    request: ReviewRequest,
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.request_review(
        db,
        attempt_id,
        principal=principal,
        reason=request.reason,
        notes=request.notes,
    )


@router.post(
    "/reviews/attempts/{attempt_id}/approve",
    response_model=AssessmentReviewResponse,
)
def approve_attempt_review(
    request: ReviewDecisionRequest,
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.approve_review(
        db,
        attempt_id,
        principal=principal,
        reason=request.reason,
        notes=request.notes,
    )


@router.post(
    "/reviews/attempts/{attempt_id}/changes",
    response_model=AssessmentReviewResponse,
)
def request_attempt_changes(
    request: ReviewDecisionRequest,
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.request_grading_changes(
        db,
        attempt_id,
        principal=principal,
        reason=request.reason,
        notes=request.notes,
    )


@router.post(
    "/reviews/attempts/{attempt_id}/regrade",
    response_model=AttemptGradingSummary,
)
def regrade_attempt(
    request: RegradeAttemptRequest,
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return grading.regrade_attempt(
        db,
        attempt_id,
        request.grades,
        principal=principal,
        reason=request.reason,
        notes=request.notes,
    )


__all__ = ["router"]
