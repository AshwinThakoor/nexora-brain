from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Concept, ConceptRelationship
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_relationship(
    db: Session,
    relationship_id: int,
) -> ConceptRelationship:
    relationship = db.get(ConceptRelationship, relationship_id)
    if relationship is None:
        raise ResourceNotFoundError("Relationship", relationship_id)
    return relationship


def _validate_concepts(
    db: Session,
    source_concept_id: int,
    target_concept_id: int,
) -> None:
    if source_concept_id == target_concept_id:
        raise ResourceValidationError(
            "Source and target concepts must be different"
        )
    if db.get(Concept, source_concept_id) is None:
        raise ResourceNotFoundError("Source concept", source_concept_id)
    if db.get(Concept, target_concept_id) is None:
        raise ResourceNotFoundError("Target concept", target_concept_id)


def _ensure_unique(
    db: Session,
    source_concept_id: int,
    target_concept_id: int,
    relationship_type: str,
    exclude_id: int | None = None,
) -> None:
    statement = select(ConceptRelationship).where(
        ConceptRelationship.source_concept_id == source_concept_id,
        ConceptRelationship.target_concept_id == target_concept_id,
        ConceptRelationship.relationship_type == relationship_type,
    )
    if exclude_id is not None:
        statement = statement.where(ConceptRelationship.id != exclude_id)
    if db.scalar(statement) is not None:
        raise ResourceConflictError("Relationship triple already exists")


def _validate_score(score: float | None) -> None:
    if score is not None and not 0.0 <= score <= 1.0:
        raise ResourceValidationError(
            "confidence_score must be between 0.0 and 1.0"
        )


def create_relationship(
    db: Session,
    values: Mapping[str, Any],
) -> ConceptRelationship:
    data = dict(values)
    source_id = data["source_concept_id"]
    target_id = data["target_concept_id"]
    relationship_type = data["relationship_type"]
    _validate_concepts(db, source_id, target_id)
    _ensure_unique(db, source_id, target_id, relationship_type)
    _validate_score(data.get("confidence_score"))
    relationship = ConceptRelationship(**data)
    db.add(relationship)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Relationship triple already exists") from exc
    db.refresh(relationship)
    return relationship


def list_relationships(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    source_concept_id: int | None = None,
    target_concept_id: int | None = None,
    relationship_type: str | None = None,
    min_confidence_score: float | None = None,
) -> tuple[list[ConceptRelationship], int]:
    filters = []
    if source_concept_id is not None:
        filters.append(
            ConceptRelationship.source_concept_id == source_concept_id
        )
    if target_concept_id is not None:
        filters.append(
            ConceptRelationship.target_concept_id == target_concept_id
        )
    if relationship_type:
        filters.append(
            ConceptRelationship.relationship_type == relationship_type
        )
    if min_confidence_score is not None:
        filters.append(
            ConceptRelationship.confidence_score >= min_confidence_score
        )

    total = db.scalar(
        select(func.count()).select_from(ConceptRelationship).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(ConceptRelationship)
            .where(*filters)
            .order_by(ConceptRelationship.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_relationship(
    db: Session,
    relationship_id: int,
    values: Mapping[str, Any],
) -> ConceptRelationship:
    relationship = get_relationship(db, relationship_id)
    data = dict(values)
    if not data:
        return relationship

    source_id = data.get(
        "source_concept_id",
        relationship.source_concept_id,
    )
    target_id = data.get(
        "target_concept_id",
        relationship.target_concept_id,
    )
    relationship_type = data.get(
        "relationship_type",
        relationship.relationship_type,
    )
    if source_id is None or target_id is None or relationship_type is None:
        raise ResourceValidationError(
            "Relationship endpoints and type cannot be null"
        )
    _validate_concepts(db, source_id, target_id)
    _ensure_unique(
        db,
        source_id,
        target_id,
        relationship_type,
        exclude_id=relationship_id,
    )
    _validate_score(data.get("confidence_score"))
    for field, value in data.items():
        setattr(relationship, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Relationship triple already exists") from exc
    db.refresh(relationship)
    return relationship


def delete_relationship(db: Session, relationship_id: int) -> None:
    relationship = get_relationship(db, relationship_id)
    db.delete(relationship)
    db.commit()


create = create_relationship
get = get_relationship
list_all = list_relationships
update = update_relationship
delete = delete_relationship
