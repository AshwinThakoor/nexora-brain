from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Tag
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_tag(db: Session, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise ResourceNotFoundError("Tag", tag_id)
    return tag


def _ensure_unique(
    db: Session,
    name: str,
    slug: str,
    exclude_id: int | None = None,
) -> None:
    statement = select(Tag).where(or_(Tag.name == name, Tag.slug == slug))
    if exclude_id is not None:
        statement = statement.where(Tag.id != exclude_id)
    if db.scalar(statement) is not None:
        raise ResourceConflictError("Tag name or slug already exists")


def create_tag(db: Session, values: Mapping[str, Any]) -> Tag:
    data = dict(values)
    _ensure_unique(db, data["name"], data["slug"])
    tag = Tag(**data)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Tag name or slug already exists") from exc
    db.refresh(tag)
    return tag


def list_tags(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    q: str | None = None,
) -> tuple[list[Tag], int]:
    filters = []
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Tag.name.ilike(pattern),
                Tag.slug.ilike(pattern),
                Tag.description.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(Tag).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Tag)
            .where(*filters)
            .order_by(Tag.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_tag(
    db: Session,
    tag_id: int,
    values: Mapping[str, Any],
) -> Tag:
    tag = get_tag(db, tag_id)
    data = dict(values)
    if not data:
        return tag

    name = data.get("name", tag.name)
    slug = data.get("slug", tag.slug)
    if name is None or slug is None:
        raise ResourceValidationError("Tag name and slug cannot be null")
    _ensure_unique(db, name, slug, exclude_id=tag_id)

    for field, value in data.items():
        setattr(tag, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Tag name or slug already exists") from exc
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int) -> None:
    tag = get_tag(db, tag_id)
    db.delete(tag)
    db.commit()


create = create_tag
get = get_tag
list_all = list_tags
update = update_tag
delete = delete_tag
