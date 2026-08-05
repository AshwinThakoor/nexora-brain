from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import Claim, Concept, ConceptRelationship, Tag
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_concept(db: Session, concept_id: int) -> Concept:
    concept = db.scalar(
        select(Concept)
        .where(Concept.id == concept_id)
        .options(selectinload(Concept.tags))
    )
    if concept is None:
        raise ResourceNotFoundError("Concept", concept_id)
    return concept


def _validate_category(db: Session, category_id: int | None) -> None:
    if category_id is None:
        return
    from ..models import Category

    if db.get(Category, category_id) is None:
        raise ResourceNotFoundError("Category", category_id)


def _ensure_unique_slug(
    db: Session,
    slug: str,
    exclude_id: int | None = None,
) -> None:
    statement = select(Concept).where(Concept.slug == slug)
    if exclude_id is not None:
        statement = statement.where(Concept.id != exclude_id)
    if db.scalar(statement) is not None:
        raise ResourceConflictError("Concept slug already exists")


def create_concept(db: Session, values: Mapping[str, Any]) -> Concept:
    data = dict(values)
    _validate_category(db, data.get("category_id"))
    _ensure_unique_slug(db, data["slug"])
    concept = Concept(**data)
    db.add(concept)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Concept slug already exists") from exc
    return get_concept(db, concept.id)


def list_concepts(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    category_id: int | None = None,
    difficulty: str | None = None,
    status: str | None = None,
    tag_id: int | None = None,
    q: str | None = None,
) -> tuple[list[Concept], int]:
    filters = []
    if category_id is not None:
        filters.append(Concept.category_id == category_id)
    if difficulty:
        filters.append(Concept.difficulty == difficulty)
    if status:
        filters.append(Concept.status == status)
    if tag_id is not None:
        filters.append(Concept.tags.any(Tag.id == tag_id))
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Concept.title.ilike(pattern),
                Concept.slug.ilike(pattern),
                Concept.summary.ilike(pattern),
                Concept.description.ilike(pattern),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(Concept).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(Concept)
            .where(*filters)
            .order_by(Concept.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_concept(
    db: Session,
    concept_id: int,
    values: Mapping[str, Any],
) -> Concept:
    concept = get_concept(db, concept_id)
    data = dict(values)
    if not data:
        return concept

    if "category_id" in data:
        _validate_category(db, data["category_id"])
    slug = data.get("slug", concept.slug)
    if slug is None:
        raise ResourceValidationError("Concept slug cannot be null")
    _ensure_unique_slug(db, slug, exclude_id=concept_id)

    required = {"title", "difficulty", "status", "version"}
    if any(field in data and data[field] is None for field in required):
        raise ResourceValidationError("Required concept fields cannot be null")
    for field, value in data.items():
        setattr(concept, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Concept slug already exists") from exc
    return get_concept(db, concept_id)


def delete_concept(db: Session, concept_id: int) -> None:
    concept = get_concept(db, concept_id)
    db.delete(concept)
    db.commit()


def attach_tag(db: Session, concept_id: int, tag_id: int) -> Concept:
    concept = get_concept(db, concept_id)
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise ResourceNotFoundError("Tag", tag_id)
    if any(existing.id == tag_id for existing in concept.tags):
        return concept
    concept.tags.append(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(
            "Tag is already attached to the concept"
        ) from exc
    return get_concept(db, concept_id)


def remove_tag(db: Session, concept_id: int, tag_id: int) -> Concept:
    concept = get_concept(db, concept_id)
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise ResourceNotFoundError("Tag", tag_id)
    attached = next((item for item in concept.tags if item.id == tag_id), None)
    if attached is None:
        raise ResourceNotFoundError(
            "Concept-tag association",
            f"{concept_id}/{tag_id}",
        )
    concept.tags.remove(attached)
    db.commit()
    return get_concept(db, concept_id)


def get_concept_claims(db: Session, concept_id: int) -> list[Claim]:
    get_concept(db, concept_id)
    return list(
        db.scalars(
            select(Claim)
            .where(Claim.concept_id == concept_id)
            .order_by(Claim.id)
        )
    )


def get_concept_relationships(
    db: Session,
    concept_id: int,
) -> list[ConceptRelationship]:
    get_concept(db, concept_id)
    return list(
        db.scalars(
            select(ConceptRelationship)
            .where(
                or_(
                    ConceptRelationship.source_concept_id == concept_id,
                    ConceptRelationship.target_concept_id == concept_id,
                )
            )
            .order_by(ConceptRelationship.id)
        )
    )


create = create_concept
get = get_concept
list_all = list_concepts
update = update_concept
delete = delete_concept
