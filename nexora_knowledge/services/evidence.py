from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Claim, Evidence, Source
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_evidence(db: Session, evidence_id: int) -> Evidence:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise ResourceNotFoundError("Evidence", evidence_id)
    return evidence


def _validate_references(
    db: Session,
    claim_id: int,
    source_id: int | None,
) -> None:
    if db.get(Claim, claim_id) is None:
        raise ResourceNotFoundError("Claim", claim_id)
    if source_id is not None and db.get(Source, source_id) is None:
        raise ResourceNotFoundError("Source", source_id)


def _validate_strength(strength: float | None) -> None:
    if strength is not None and not 0.0 <= strength <= 1.0:
        raise ResourceValidationError("strength must be between 0.0 and 1.0")


def create_evidence(db: Session, values: Mapping[str, Any]) -> Evidence:
    data = dict(values)
    _validate_references(db, data["claim_id"], data.get("source_id"))
    _validate_strength(data.get("strength"))
    evidence = Evidence(**data)
    db.add(evidence)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Evidence could not be created") from exc
    db.refresh(evidence)
    return evidence


def list_evidence(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    claim_id: int | None = None,
    source_id: int | None = None,
    evidence_type: str | None = None,
    strength: float | None = None,
) -> tuple[list[Evidence], int]:
    filters = []
    if claim_id is not None:
        filters.append(Evidence.claim_id == claim_id)
    if source_id is not None:
        filters.append(Evidence.source_id == source_id)
    if evidence_type:
        filters.append(Evidence.evidence_type == evidence_type)
    if strength is not None:
        filters.append(Evidence.strength == strength)

    total = db.scalar(
        select(func.count()).select_from(Evidence).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(Evidence)
            .where(*filters)
            .order_by(Evidence.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_evidence(
    db: Session,
    evidence_id: int,
    values: Mapping[str, Any],
) -> Evidence:
    evidence = get_evidence(db, evidence_id)
    data = dict(values)
    if not data:
        return evidence
    claim_id = data.get("claim_id", evidence.claim_id)
    source_id = data.get("source_id", evidence.source_id)
    if claim_id is None:
        raise ResourceValidationError("Evidence claim_id cannot be null")
    _validate_references(db, claim_id, source_id)
    if any(
        field in data and data[field] is None
        for field in ("evidence_type", "strength")
    ):
        raise ResourceValidationError(
            "Evidence evidence_type and strength cannot be null"
        )
    _validate_strength(data.get("strength"))
    for field, value in data.items():
        setattr(evidence, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Evidence could not be updated") from exc
    db.refresh(evidence)
    return evidence


def delete_evidence(db: Session, evidence_id: int) -> None:
    evidence = get_evidence(db, evidence_id)
    db.delete(evidence)
    db.commit()


create = create_evidence
get = get_evidence
list_all = list_evidence
update = update_evidence
delete = delete_evidence
