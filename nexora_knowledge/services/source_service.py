from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Source,
    SourceAlias,
    SourceLicense,
    SourceOrganization,
    SourceVersion,
    Tag,
)
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


_SORT_COLUMNS = {
    "id": Source.id,
    "slug": Source.slug,
    "title": Source.title,
    "source_type": Source.source_type,
    "language": Source.language,
    "trust_level": Source.trust_level,
    "publication_date": Source.publication_date,
    "created_at": Source.created_at,
    "updated_at": Source.updated_at,
}
_NON_NULLABLE_FIELDS = {
    "slug",
    "title",
    "source_type",
    "language",
    "trust_level",
    "active",
    "archived",
}


def _source_query():
    return (
        select(Source)
        .options(
            selectinload(Source.organization),
            selectinload(Source.license_record),
            selectinload(Source.aliases),
            selectinload(Source.versions),
            selectinload(Source.tags),
        )
        .execution_options(populate_existing=True)
    )


def get_source(db: Session, source_id: int) -> Source:
    source = db.scalar(_source_query().where(Source.id == source_id))
    if source is None:
        raise ResourceNotFoundError("Source", source_id)
    return source


def get_by_slug(db: Session, slug: str) -> Source:
    normalized = slug.strip().casefold()
    source = db.scalar(
        _source_query().where(func.lower(Source.slug) == normalized)
    )
    if source is None:
        raise ResourceNotFoundError("Source slug", slug)
    return source


def _normalize_values(values: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(values)
    for field in (
        "slug",
        "title",
        "subtitle",
        "language",
        "publisher",
        "author",
        "isbn",
        "doi",
        "url",
        "external_identifier",
    ):
        value = data.get(field)
        if isinstance(value, str):
            data[field] = value.strip()
    for field in ("source_type", "trust_level"):
        value = data.get(field)
        if value is not None:
            data[field] = str(value)
    if data.get("doi"):
        data["doi"] = data["doi"].casefold()
    return data


def _ensure_unique(
    db: Session,
    data: Mapping[str, Any],
    *,
    exclude_id: int | None = None,
) -> None:
    checks = (
        ("slug", Source.slug, "Source slug already exists"),
        ("doi", Source.doi, "Source DOI already exists"),
        ("isbn", Source.isbn, "Source ISBN already exists"),
    )
    for field, column, message in checks:
        value = data.get(field)
        if value in (None, ""):
            continue
        statement = select(Source.id).where(
            func.lower(column) == str(value).casefold()
        )
        if exclude_id is not None:
            statement = statement.where(Source.id != exclude_id)
        if db.scalar(statement) is not None:
            raise ResourceConflictError(message)


def _validate_references(db: Session, data: Mapping[str, Any]) -> None:
    organization_id = data.get("organization_id")
    if (
        organization_id is not None
        and db.get(SourceOrganization, organization_id) is None
    ):
        raise ResourceNotFoundError(
            "Source organization",
            organization_id,
        )
    license_id = data.get("license_id")
    if license_id is not None and db.get(SourceLicense, license_id) is None:
        raise ResourceNotFoundError("Source license", license_id)


def _validate_lifecycle(
    data: Mapping[str, Any],
    *,
    source: Source | None = None,
) -> None:
    active = data.get("active", source.active if source is not None else True)
    archived = data.get(
        "archived",
        source.archived if source is not None else False,
    )
    if active and archived:
        raise ResourceValidationError(
            "An archived source cannot be active"
        )


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def create_source(db: Session, values: Mapping[str, Any]) -> Source:
    data = _normalize_values(values)
    _ensure_unique(db, data)
    _validate_references(db, data)
    _validate_lifecycle(data)
    source = Source(**data)
    db.add(source)
    _commit(db, "Source identifiers must be unique")
    return get_source(db, source.id)


def update_source(
    db: Session,
    source_id: int,
    values: Mapping[str, Any],
) -> Source:
    source = get_source(db, source_id)
    data = _normalize_values(values)
    if not data:
        return source
    null_fields = sorted(
        field
        for field in _NON_NULLABLE_FIELDS
        if field in data and data[field] is None
    )
    if null_fields:
        raise ResourceValidationError(
            f"Source fields cannot be null: {', '.join(null_fields)}"
        )
    _ensure_unique(db, data, exclude_id=source.id)
    _validate_references(db, data)
    _validate_lifecycle(data, source=source)
    for field, value in data.items():
        setattr(source, field, value)
    _commit(db, "Source identifiers must be unique")
    return get_source(db, source.id)


def archive_source(db: Session, source_id: int) -> Source:
    source = get_source(db, source_id)
    source.active = False
    source.archived = True
    _commit(db, "Source could not be archived")
    return get_source(db, source.id)


def restore_source(db: Session, source_id: int) -> Source:
    source = get_source(db, source_id)
    source.active = True
    source.archived = False
    _commit(db, "Source could not be restored")
    return get_source(db, source.id)


def _identity_filter(
    column,
    value: int | str,
    text_columns: tuple,
):
    if isinstance(value, int) or str(value).isdigit():
        return column == int(value)
    normalized = str(value).casefold()
    return or_(*(func.lower(item) == normalized for item in text_columns))


def search_sources(
    db: Session,
    *,
    q: str | None = None,
    source_type: str | None = None,
    organization: int | str | None = None,
    language: str | None = None,
    trust: str | None = None,
    tag: int | str | None = None,
    active: bool | None = None,
    archived: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Source], int]:
    if offset < 0:
        raise ResourceValidationError("Source search offset cannot be negative")
    if not 1 <= limit <= 200:
        raise ResourceValidationError(
            "Source search limit must be between 1 and 200"
        )
    sort_column = _SORT_COLUMNS.get(sort_by)
    if sort_column is None:
        raise ResourceValidationError("Unsupported source sort field")
    if sort_order not in {"asc", "desc"}:
        raise ResourceValidationError(
            "Source sort order must be 'asc' or 'desc'"
        )

    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Source.title.ilike(pattern),
                Source.subtitle.ilike(pattern),
                Source.description.ilike(pattern),
                Source.author.ilike(pattern),
                Source.publisher.ilike(pattern),
                Source.slug.ilike(pattern),
                Source.isbn.ilike(pattern),
                Source.doi.ilike(pattern),
                Source.url.ilike(pattern),
                Source.external_identifier.ilike(pattern),
                Source.aliases.any(SourceAlias.alias.ilike(pattern)),
            )
        )
    if source_type is not None:
        filters.append(
            func.lower(Source.source_type) == str(source_type).casefold()
        )
    if organization is not None:
        filters.append(
            Source.organization.has(
                _identity_filter(
                    SourceOrganization.id,
                    organization,
                    (SourceOrganization.slug, SourceOrganization.name),
                )
            )
        )
    if language is not None:
        filters.append(func.lower(Source.language) == language.casefold())
    if trust is not None:
        filters.append(
            func.lower(Source.trust_level) == str(trust).casefold()
        )
    if tag is not None:
        filters.append(
            Source.tags.any(
                _identity_filter(
                    Tag.id,
                    tag,
                    (Tag.slug, Tag.name),
                )
            )
        )
    if active is not None:
        filters.append(Source.active.is_(active))
    if archived is not None:
        filters.append(Source.archived.is_(archived))

    total = db.scalar(
        select(func.count()).select_from(Source).where(*filters)
    ) or 0
    order_expression = (
        asc(sort_column) if sort_order == "asc" else desc(sort_column)
    )
    items = list(
        db.scalars(
            select(Source)
            .where(*filters)
            .order_by(order_expression, Source.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def add_alias(db: Session, source_id: int, alias: str) -> SourceAlias:
    source = get_source(db, source_id)
    normalized = alias.strip()
    if not normalized or len(normalized) > 500:
        raise ResourceValidationError(
            "Source alias must contain between 1 and 500 characters"
        )
    duplicate = db.scalar(
        select(SourceAlias.id).where(
            SourceAlias.source_id == source.id,
            func.lower(SourceAlias.alias) == normalized.casefold(),
        )
    )
    if duplicate is not None:
        raise ResourceConflictError("Source alias already exists")
    record = SourceAlias(source_id=source.id, alias=normalized)
    db.add(record)
    _commit(db, "Source alias already exists")
    db.refresh(record)
    return record


def add_version(
    db: Session,
    source_id: int,
    values: Mapping[str, Any],
) -> SourceVersion:
    source = get_source(db, source_id)
    data = dict(values)
    version = str(data.get("version", "")).strip()
    checksum = str(data.get("checksum", "")).strip().casefold()
    if not version or len(version) > 100:
        raise ResourceValidationError(
            "Source version must contain between 1 and 100 characters"
        )
    if not checksum or len(checksum) > 128:
        raise ResourceValidationError(
            "Source checksum must contain between 1 and 128 characters"
        )
    duplicate = db.scalar(
        select(SourceVersion.id).where(
            SourceVersion.source_id == source.id,
            or_(
                func.lower(SourceVersion.version) == version.casefold(),
                func.lower(SourceVersion.checksum) == checksum,
            ),
        )
    )
    if duplicate is not None:
        raise ResourceConflictError(
            "Source version or checksum already exists"
        )
    data["version"] = version
    data["checksum"] = checksum
    record = SourceVersion(source_id=source.id, **data)
    db.add(record)
    _commit(db, "Source version or checksum already exists")
    db.refresh(record)
    return record


def _resolve_tags(db: Session, tag_ids: Iterable[int]) -> list[Tag]:
    unique_ids = sorted({int(tag_id) for tag_id in tag_ids})
    if not unique_ids:
        return []
    tags = list(db.scalars(select(Tag).where(Tag.id.in_(unique_ids))))
    found_ids = {tag.id for tag in tags}
    missing = [tag_id for tag_id in unique_ids if tag_id not in found_ids]
    if missing:
        raise ResourceNotFoundError("Tag", missing[0])
    return tags


def assign_tags(
    db: Session,
    source_id: int,
    tag_ids: Iterable[int],
) -> Source:
    source = get_source(db, source_id)
    existing_ids = {tag.id for tag in source.tags}
    for tag in _resolve_tags(db, tag_ids):
        if tag.id not in existing_ids:
            source.tags.append(tag)
    _commit(db, "Source tags could not be assigned")
    return get_source(db, source.id)


def remove_tags(
    db: Session,
    source_id: int,
    tag_ids: Iterable[int],
) -> Source:
    source = get_source(db, source_id)
    requested_ids = {tag.id for tag in _resolve_tags(db, tag_ids)}
    source.tags[:] = [
        tag for tag in source.tags if tag.id not in requested_ids
    ]
    _commit(db, "Source tags could not be removed")
    return get_source(db, source.id)


__all__ = [
    "add_alias",
    "add_version",
    "archive_source",
    "assign_tags",
    "create_source",
    "get_by_slug",
    "get_source",
    "remove_tags",
    "restore_source",
    "search_sources",
    "update_source",
]
