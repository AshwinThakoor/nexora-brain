from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import Claim, Concept
from ..models.enums import KnowledgeLifecycleStatus
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_claim(db: Session, claim_id: int) -> Claim:
    claim = db.scalar(
        select(Claim)
        .where(Claim.id == claim_id)
        .options(selectinload(Claim.evidence_records))
    )
    if claim is None:
        raise ResourceNotFoundError("Claim", claim_id)
    return claim


def _validate_concept(db: Session, concept_id: int) -> None:
    if db.get(Concept, concept_id) is None:
        raise ResourceNotFoundError("Concept", concept_id)


def _validate_score(score: float | None) -> None:
    if score is not None and not 0.0 <= score <= 1.0:
        raise ResourceValidationError(
            "confidence_score must be between 0.0 and 1.0"
        )


def _validate_lifecycle_status(status: object | None) -> None:
    if status is None:
        return
    value = getattr(status, "value", status)
    allowed = {item.value for item in KnowledgeLifecycleStatus}
    if value not in allowed:
        raise ResourceValidationError(
            "lifecycle_status must be a valid KnowledgeLifecycleStatus"
        )


def create_claim(db: Session, values: Mapping[str, Any]) -> Claim:
    data = dict(values)
    _validate_concept(db, data["concept_id"])
    _validate_score(data.get("confidence_score"))
    _validate_lifecycle_status(data.get("lifecycle_status"))
    claim = Claim(**data)
    db.add(claim)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Claim could not be created") from exc
    return get_claim(db, claim.id)


def list_claims(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    concept_id: int | None = None,
    claim_type: str | None = None,
    status: str | None = None,
    min_confidence_score: float | None = None,
    q: str | None = None,
) -> tuple[list[Claim], int]:
    filters = []
    if concept_id is not None:
        filters.append(Claim.concept_id == concept_id)
    if claim_type:
        filters.append(Claim.claim_type == claim_type)
    if status:
        filters.append(Claim.status == status)
    if min_confidence_score is not None:
        filters.append(Claim.confidence_score >= min_confidence_score)
    if q:
        filters.append(Claim.statement.ilike(f"%{q}%"))

    total = db.scalar(
        select(func.count()).select_from(Claim).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(Claim)
            .where(*filters)
            .order_by(Claim.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_claim(
    db: Session,
    claim_id: int,
    values: Mapping[str, Any],
) -> Claim:
    claim = get_claim(db, claim_id)
    data = dict(values)
    if not data:
        return claim
    if "concept_id" in data:
        if data["concept_id"] is None:
            raise ResourceValidationError("Claim concept_id cannot be null")
        _validate_concept(db, data["concept_id"])
    if any(
        field in data and data[field] is None
        for field in (
            "statement",
            "claim_type",
            "status",
            "lifecycle_status",
        )
    ):
        raise ResourceValidationError("Required claim fields cannot be null")
    _validate_score(data.get("confidence_score"))
    _validate_lifecycle_status(data.get("lifecycle_status"))
    for field, value in data.items():
        setattr(claim, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Claim could not be updated") from exc
    return get_claim(db, claim_id)


def delete_claim(db: Session, claim_id: int) -> None:
    claim = get_claim(db, claim_id)
    db.delete(claim)
    db.commit()


create = create_claim
get = get_claim
list_all = list_claims
update = update_claim
delete = delete_claim
