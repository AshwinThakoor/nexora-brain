from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Learner
from ..schemas.api_curriculum import AcademyPage
from ..schemas.api_learning import LearnerAttemptDetail
from ..schemas.grading import GradingAuditEventResponse
from ..schemas.learning import LearnerProgressSummary, LearnerRead
from ..services import grading, learning
from ..services.authorization import Principal, require_admin
from ..services.exceptions import ResourceNotFoundError
from .academy_learning import _attempt_payload
from .dependencies import get_current_principal, get_db


router = APIRouter(
    prefix="/api/v1/academy/admin",
    tags=["academy-admin"],
)


@router.get("/learners", response_model=AcademyPage[LearnerRead])
def list_learners(
    learner_status: str | None = Query(
        default=None,
        alias="status",
        max_length=50,
    ),
    q: str | None = Query(default=None, max_length=320),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    require_admin(principal)
    statement = select(Learner)
    if learner_status is not None:
        statement = statement.where(Learner.status == learner_status)
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Learner.display_name).like(term),
                func.lower(Learner.email).like(term),
                func.lower(Learner.external_user_id).like(term),
            )
        )
    total = db.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    items = list(
        db.scalars(
            statement.order_by(Learner.id).offset(offset).limit(limit)
        )
    )
    return {
        "items": items,
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
        "skip": offset,
    }


@router.get("/learners/{learner_id}", response_model=LearnerRead)
def get_learner(
    learner_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    require_admin(principal)
    learner = db.get(Learner, learner_id)
    if learner is None:
        raise ResourceNotFoundError("Learner", learner_id)
    return learner


@router.get(
    "/learners/{learner_id}/progress",
    response_model=LearnerProgressSummary,
)
def get_learner_progress(
    learner_id: int = Path(gt=0),
    recent_limit: int = Query(default=10, ge=0, le=50),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    require_admin(principal)
    return learning.get_learner_progress_summary(
        db, learner_id, recent_limit=recent_limit
    )


@router.get(
    "/assessment-attempts/{attempt_id}",
    response_model=LearnerAttemptDetail,
)
def get_assessment_attempt(
    attempt_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    require_admin(principal)
    return _attempt_payload(
        grading.get_attempt_for_staff(
            db, attempt_id, principal=principal
        )
    )


@router.get(
    "/audit-events",
    response_model=AcademyPage[GradingAuditEventResponse],
)
def audit_events(
    attempt_id: int | None = Query(default=None, gt=0),
    answer_id: int | None = Query(default=None, gt=0),
    event_type: str | None = Query(default=None, max_length=100),
    actor_external_id: str | None = Query(default=None, max_length=255),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    require_admin(principal)
    events = grading.list_audit_events(
        db,
        principal=principal,
        attempt_id=attempt_id,
        answer_id=answer_id,
        event_type=event_type,
        actor_external_id=actor_external_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
    total = grading.count_audit_events(
        db,
        principal=principal,
        attempt_id=attempt_id,
        answer_id=answer_id,
        event_type=event_type,
        actor_external_id=actor_external_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "items": events,
        "total": total,
        "limit": limit,
        "offset": offset,
        "skip": offset,
    }


__all__ = ["router"]
