from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Source
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_source(db: Session, source_id: int) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise ResourceNotFoundError("Source", source_id)
    return source


def _validate(values: Mapping[str, Any]) -> None:
    for field in ("quality_score", "trust_score"):
        value = values.get(field)
        if value is not None and not 0.0 <= value <= 1.0:
            raise ResourceValidationError(f"{field} must be between 0.0 and 1.0")
    publication_year = values.get("publication_year")
    if publication_year is not None and not (
        1000 <= publication_year <= datetime.now(timezone.utc).year
    ):
        raise ResourceValidationError("publication_year is outside the valid range")


def create_source(db: Session, values: Mapping[str, Any]) -> Source:
    data = dict(values)
    _validate(data)
    source = Source(**data)
    db.add(source)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Source could not be created") from exc
    db.refresh(source)
    return source


def list_sources(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    source_type: str | None = None,
    author: str | None = None,
    q: str | None = None,
) -> tuple[list[Source], int]:
    filters = []
    if source_type:
        filters.append(Source.source_type == source_type)
    if author:
        filters.append(Source.author == author)
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Source.title.ilike(pattern),
                Source.author.ilike(pattern),
                Source.publisher.ilike(pattern),
                Source.url.ilike(pattern),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(Source).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(Source)
            .where(*filters)
            .order_by(Source.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_source(
    db: Session,
    source_id: int,
    values: Mapping[str, Any],
) -> Source:
    source = get_source(db, source_id)
    data = dict(values)
    if not data:
        return source
    if any(
        field in data and data[field] is None
        for field in ("title", "source_type")
    ):
        raise ResourceValidationError("Source title and source_type cannot be null")
    _validate(data)
    for field, value in data.items():
        setattr(source, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError("Source could not be updated") from exc
    db.refresh(source)
    return source


def delete_source(db: Session, source_id: int) -> None:
    source = get_source(db, source_id)
    db.delete(source)
    db.commit()


create = create_source
get = get_source
list_all = list_sources
update = update_source
delete = delete_source
