from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Document,
    DocumentFile,
    DocumentIdentifier,
    DocumentRelationship,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    ImportBatch,
    ProcessingStatus,
    RelationshipType,
    Source,
    Tag,
)
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


_SORT_COLUMNS = {
    "id": Document.id,
    "slug": Document.slug,
    "source_id": Document.source_id,
    "title": Document.title,
    "document_type": Document.document_type,
    "language": Document.language,
    "publication_date": Document.publication_date,
    "publication_year": Document.publication_year,
    "status": Document.status,
    "created_at": Document.created_at,
    "updated_at": Document.updated_at,
}
_NON_NULLABLE_FIELDS = {
    "slug",
    "source_id",
    "title",
    "document_type",
    "language",
    "status",
    "active",
    "archived",
}


def _document_query():
    return (
        select(Document)
        .options(
            selectinload(Document.source).selectinload(Source.license_record),
            selectinload(Document.versions).selectinload(
                DocumentVersion.files
            ),
            selectinload(Document.versions).selectinload(
                DocumentVersion.stored_files
            ),
            selectinload(Document.files),
            selectinload(Document.stored_files),
            selectinload(Document.identifiers),
            selectinload(Document.relationships),
            selectinload(Document.incoming_relationships),
            selectinload(Document.tags),
        )
        .execution_options(populate_existing=True)
    )


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def _normalize_document_values(values: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(values)
    for field in (
        "slug",
        "title",
        "subtitle",
        "author_override",
        "publisher_override",
        "language",
    ):
        value = data.get(field)
        if isinstance(value, str):
            data[field] = value.strip()
    enum_fields = {
        "document_type": DocumentType,
        "status": DocumentStatus,
    }
    for field, enum_type in enum_fields.items():
        value = data.get(field)
        if value is not None:
            normalized = str(value).strip().casefold()
            try:
                data[field] = enum_type(normalized).value
            except ValueError as exc:
                raise ResourceValidationError(
                    f"Unsupported document {field.replace('_', ' ')}"
                ) from exc
    if isinstance(data.get("slug"), str):
        data["slug"] = data["slug"].casefold()
    if isinstance(data.get("language"), str):
        data["language"] = data["language"].casefold()
    return data


def _validate_source(db: Session, source_id: int) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise ResourceNotFoundError("Source", source_id)
    return source


def _validate_lifecycle(
    data: Mapping[str, Any],
    *,
    document: Document | None = None,
) -> None:
    active = data.get(
        "active",
        document.active if document is not None else True,
    )
    archived = data.get(
        "archived",
        document.archived if document is not None else False,
    )
    status = data.get(
        "status",
        document.status
        if document is not None
        else DocumentStatus.REGISTERED.value,
    )
    if active and archived:
        raise ResourceValidationError(
            "An archived document cannot be active"
        )
    if archived and status != DocumentStatus.ARCHIVED.value:
        raise ResourceValidationError(
            "An archived document must have archived status"
        )
    publication_date = data.get(
        "publication_date",
        document.publication_date if document is not None else None,
    )
    publication_year = data.get(
        "publication_year",
        document.publication_year if document is not None else None,
    )
    if (
        publication_date is not None
        and publication_year is not None
        and publication_date.year != publication_year
    ):
        raise ResourceValidationError(
            "Publication year must match the publication date year"
        )


def _ensure_unique_slug(
    db: Session,
    slug: str | None,
    *,
    exclude_id: int | None = None,
) -> None:
    if not slug:
        return
    statement = select(Document.id).where(
        func.lower(Document.slug) == slug.casefold()
    )
    if exclude_id is not None:
        statement = statement.where(Document.id != exclude_id)
    if db.scalar(statement) is not None:
        raise ResourceConflictError("Document slug already exists")


def get_document(db: Session, document_id: int) -> Document:
    document = db.scalar(
        _document_query().where(Document.id == document_id)
    )
    if document is None:
        raise ResourceNotFoundError("Document", document_id)
    return document


def register_document(db: Session, values: Mapping[str, Any]) -> Document:
    data = _normalize_document_values(values)
    try:
        source_id = int(data["source_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ResourceValidationError("Document source ID is required") from exc
    data["source_id"] = source_id
    _validate_source(db, source_id)
    _ensure_unique_slug(db, data.get("slug"))
    _validate_lifecycle(data)
    document = Document(**data)
    db.add(document)
    _commit(db, "Document slug or UUID already exists")
    return get_document(db, document.id)


def update_document(
    db: Session,
    document_id: int,
    values: Mapping[str, Any],
) -> Document:
    document = get_document(db, document_id)
    data = _normalize_document_values(values)
    if not data:
        return document
    null_fields = sorted(
        field
        for field in _NON_NULLABLE_FIELDS
        if field in data and data[field] is None
    )
    if null_fields:
        raise ResourceValidationError(
            f"Document fields cannot be null: {', '.join(null_fields)}"
        )
    if "source_id" in data:
        _validate_source(db, int(data["source_id"]))
    _ensure_unique_slug(
        db,
        data.get("slug"),
        exclude_id=document.id,
    )
    _validate_lifecycle(data, document=document)
    for field, value in data.items():
        setattr(document, field, value)
    _commit(db, "Document slug or UUID already exists")
    return get_document(db, document.id)


def archive_document(db: Session, document_id: int) -> Document:
    document = get_document(db, document_id)
    document.active = False
    document.archived = True
    document.status = DocumentStatus.ARCHIVED.value
    _commit(db, "Document could not be archived")
    return get_document(db, document.id)


def restore_document(db: Session, document_id: int) -> Document:
    document = get_document(db, document_id)
    document.active = True
    document.archived = False
    if document.status == DocumentStatus.ARCHIVED.value:
        document.status = DocumentStatus.REGISTERED.value
    _commit(db, "Document could not be restored")
    return get_document(db, document.id)


def register_version(
    db: Session,
    document_id: int,
    values: Mapping[str, Any],
) -> DocumentVersion:
    document = get_document(db, document_id)
    data = dict(values)
    version = str(data.get("version", "")).strip()
    checksum = str(data.get("checksum", "")).strip().casefold()
    if not version or len(version) > 100:
        raise ResourceValidationError(
            "Document version must contain between 1 and 100 characters"
        )
    if not checksum or len(checksum) > 128:
        raise ResourceValidationError(
            "Document checksum must contain between 1 and 128 characters"
        )
    duplicate = db.scalar(
        select(DocumentVersion.id).where(
            DocumentVersion.document_id == document.id,
            or_(
                func.lower(DocumentVersion.version) == version.casefold(),
                func.lower(DocumentVersion.checksum) == checksum,
            ),
        )
    )
    if duplicate is not None:
        raise ResourceConflictError(
            "Document version or checksum already exists"
        )

    current = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.is_current.is_(True),
        )
    )
    make_current = bool(data.pop("is_current", True)) or current is None
    if make_current and current is not None:
        current.is_current = False
        db.flush()

    data["version"] = version
    data["checksum"] = checksum
    data["is_current"] = make_current
    record = DocumentVersion(document_id=document.id, **data)
    db.add(record)
    _commit(db, "Document version or checksum already exists")
    db.refresh(record)
    return record


def set_current_version(
    db: Session,
    document_id: int,
    version_id: int,
) -> DocumentVersion:
    get_document(db, document_id)
    target = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    if target is None:
        raise ResourceNotFoundError("Document version", version_id)
    if target.is_current:
        return target

    current_versions = list(
        db.scalars(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_current.is_(True),
            )
        )
    )
    for current in current_versions:
        current.is_current = False
    db.flush()
    target.is_current = True
    _commit(db, "Document current version could not be changed")
    db.refresh(target)
    return target


def register_file_metadata(
    db: Session,
    document_version_id: int | Mapping[str, Any],
    values: Mapping[str, Any] | None = None,
) -> DocumentFile:
    if isinstance(document_version_id, Mapping):
        data = dict(document_version_id)
        raw_version_id = data.pop("document_version_id", None)
        if raw_version_id is None:
            raise ResourceValidationError(
                "Document version ID is required for file metadata"
            )
        version_id = int(raw_version_id)
    else:
        version_id = int(document_version_id)
        data = dict(values or {})
        data.pop("document_version_id", None)

    if db.get(DocumentVersion, version_id) is None:
        raise ResourceNotFoundError("Document version", version_id)
    for field in ("original_filename", "mime_type", "extension", "sha256"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ResourceValidationError(
                f"Document file {field} is required"
            )
        data[field] = value.strip()
    data["mime_type"] = data["mime_type"].casefold()
    data["extension"] = data["extension"].casefold().lstrip(".")
    data["sha256"] = data["sha256"].casefold()
    if len(data["sha256"]) != 64 or any(
        character not in "0123456789abcdef"
        for character in data["sha256"]
    ):
        raise ResourceValidationError(
            "Document file SHA-256 must contain 64 hexadecimal characters"
        )
    size_bytes = data.get("size_bytes")
    if not isinstance(size_bytes, int) or size_bytes < 0:
        raise ResourceValidationError(
            "Document file size must be a non-negative integer"
        )
    page_count = data.get("page_count")
    if page_count is not None and (
        not isinstance(page_count, int) or page_count <= 0
    ):
        raise ResourceValidationError(
            "Document file page count must be a positive integer"
        )
    if data.get("processing_status") is not None:
        normalized_status = str(data["processing_status"]).casefold()
        try:
            data["processing_status"] = ProcessingStatus(
                normalized_status
            ).value
        except ValueError as exc:
            raise ResourceValidationError(
                "Unsupported document file processing status"
            ) from exc

    record = DocumentFile(document_version_id=version_id, **data)
    db.add(record)
    _commit(db, "Document file metadata could not be registered")
    db.refresh(record)
    return record


def add_identifier(
    db: Session,
    document_id: int,
    values: Mapping[str, Any],
) -> DocumentIdentifier:
    get_document(db, document_id)
    identifier_type = str(values.get("identifier_type", "")).strip().upper()
    identifier_value = str(values.get("identifier_value", "")).strip()
    if not identifier_type or len(identifier_type) > 100:
        raise ResourceValidationError(
            "Identifier type must contain between 1 and 100 characters"
        )
    if not identifier_value or len(identifier_value) > 500:
        raise ResourceValidationError(
            "Identifier value must contain between 1 and 500 characters"
        )
    duplicate = db.scalar(
        select(DocumentIdentifier.id).where(
            func.lower(DocumentIdentifier.identifier_type)
            == identifier_type.casefold(),
            func.lower(DocumentIdentifier.identifier_value)
            == identifier_value.casefold(),
        )
    )
    if duplicate is not None:
        raise ResourceConflictError("Document identifier already exists")
    record = DocumentIdentifier(
        document_id=document_id,
        identifier_type=identifier_type,
        identifier_value=identifier_value,
    )
    db.add(record)
    _commit(db, "Document identifier already exists")
    db.refresh(record)
    return record


def remove_identifier(
    db: Session,
    document_id: int,
    identifier_id: int,
) -> None:
    get_document(db, document_id)
    record = db.scalar(
        select(DocumentIdentifier).where(
            DocumentIdentifier.id == identifier_id,
            DocumentIdentifier.document_id == document_id,
        )
    )
    if record is None:
        raise ResourceNotFoundError("Document identifier", identifier_id)
    db.delete(record)
    _commit(db, "Document identifier could not be removed")


def create_relationship(
    db: Session,
    document_id: int,
    values: Mapping[str, Any],
) -> DocumentRelationship:
    get_document(db, document_id)
    try:
        target_id = int(values.get("target_document_id", 0))
    except (TypeError, ValueError) as exc:
        raise ResourceValidationError(
            "Target document ID is required"
        ) from exc
    if target_id <= 0:
        raise ResourceValidationError("Target document ID is required")
    if target_id == document_id:
        raise ResourceValidationError(
            "A document cannot have a relationship with itself"
        )
    if db.get(Document, target_id) is None:
        raise ResourceNotFoundError("Target document", target_id)
    normalized_type = str(
        values.get("relationship_type", "")
    ).strip().casefold()
    if not normalized_type:
        raise ResourceValidationError("Document relationship type is required")
    try:
        relationship_type = RelationshipType(normalized_type).value
    except ValueError as exc:
        raise ResourceValidationError(
            "Unsupported document relationship type"
        ) from exc
    duplicate = db.scalar(
        select(DocumentRelationship.id).where(
            DocumentRelationship.source_document_id == document_id,
            DocumentRelationship.target_document_id == target_id,
            DocumentRelationship.relationship_type == relationship_type,
        )
    )
    if duplicate is not None:
        raise ResourceConflictError("Document relationship already exists")
    record = DocumentRelationship(
        source_document_id=document_id,
        target_document_id=target_id,
        relationship_type=relationship_type,
    )
    db.add(record)
    _commit(db, "Document relationship already exists")
    db.refresh(record)
    return record


def _identity_filter(column, value: int | str, text_columns: tuple):
    if isinstance(value, int) or str(value).isdigit():
        return column == int(value)
    normalized = str(value).strip().casefold()
    return or_(*(func.lower(item) == normalized for item in text_columns))


def search_documents(
    db: Session,
    *,
    q: str | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    author: str | None = None,
    language: str | None = None,
    source: int | str | None = None,
    status: str | None = None,
    document_type: str | None = None,
    publication_year: int | None = None,
    identifier: str | None = None,
    tag: int | str | None = None,
    active: bool | None = None,
    archived: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Document], int]:
    if offset < 0:
        raise ResourceValidationError(
            "Document search offset cannot be negative"
        )
    if not 1 <= limit <= 200:
        raise ResourceValidationError(
            "Document search limit must be between 1 and 200"
        )
    sort_column = _SORT_COLUMNS.get(sort_by)
    if sort_column is None:
        raise ResourceValidationError("Unsupported document sort field")
    if sort_order not in {"asc", "desc"}:
        raise ResourceValidationError(
            "Document sort order must be 'asc' or 'desc'"
        )

    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Document.slug.ilike(pattern),
                Document.title.ilike(pattern),
                Document.subtitle.ilike(pattern),
                Document.abstract.ilike(pattern),
                Document.description.ilike(pattern),
                Document.author_override.ilike(pattern),
                Document.publisher_override.ilike(pattern),
                Document.identifiers.any(
                    or_(
                        DocumentIdentifier.identifier_type.ilike(pattern),
                        DocumentIdentifier.identifier_value.ilike(pattern),
                    )
                ),
                Document.source.has(
                    or_(
                        Source.title.ilike(pattern),
                        Source.slug.ilike(pattern),
                        Source.author.ilike(pattern),
                    )
                ),
            )
        )
    if title is not None:
        filters.append(Document.title.ilike(f"%{title.strip()}%"))
    if subtitle is not None:
        filters.append(Document.subtitle.ilike(f"%{subtitle.strip()}%"))
    if author is not None:
        pattern = f"%{author.strip()}%"
        filters.append(
            or_(
                Document.author_override.ilike(pattern),
                Document.source.has(Source.author.ilike(pattern)),
            )
        )
    if language is not None:
        filters.append(func.lower(Document.language) == language.casefold())
    if source is not None:
        filters.append(
            Document.source.has(
                _identity_filter(
                    Source.id,
                    source,
                    (Source.slug, Source.title),
                )
            )
        )
    if status is not None:
        filters.append(
            func.lower(Document.status) == str(status).casefold()
        )
    if document_type is not None:
        filters.append(
            func.lower(Document.document_type)
            == str(document_type).casefold()
        )
    if publication_year is not None:
        filters.append(Document.publication_year == publication_year)
    if identifier is not None:
        pattern = f"%{identifier.strip()}%"
        filters.append(
            Document.identifiers.any(
                or_(
                    DocumentIdentifier.identifier_type.ilike(pattern),
                    DocumentIdentifier.identifier_value.ilike(pattern),
                )
            )
        )
    if tag is not None:
        filters.append(
            Document.tags.any(
                _identity_filter(Tag.id, tag, (Tag.slug, Tag.name))
            )
        )
    if active is not None:
        filters.append(Document.active.is_(active))
    if archived is not None:
        filters.append(Document.archived.is_(archived))

    total = db.scalar(
        select(func.count()).select_from(Document).where(*filters)
    ) or 0
    order_expression = (
        asc(sort_column) if sort_order == "asc" else desc(sort_column)
    )
    items = list(
        db.scalars(
            select(Document)
            .where(*filters)
            .order_by(order_expression, Document.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def list_import_batches(
    db: Session,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[ImportBatch], int]:
    if offset < 0 or not 1 <= limit <= 200:
        raise ResourceValidationError(
            "Import batch pagination values are invalid"
        )
    filters = []
    if status is not None:
        filters.append(
            func.lower(ImportBatch.status) == str(status).casefold()
        )
    total = db.scalar(
        select(func.count()).select_from(ImportBatch).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(ImportBatch)
            .where(*filters)
            .order_by(desc(ImportBatch.created_at), ImportBatch.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def validate_ingestion_eligibility(
    db: Session,
    document_id: int,
) -> bool:
    document = get_document(db, document_id)
    reasons: list[str] = []
    source = document.source
    if not source.active or source.archived:
        reasons.append("source is not active")
    if (
        source.license_record is None
        or not source.license_record.allows_ingestion
    ):
        reasons.append("source license does not allow ingestion")
    if not document.active:
        reasons.append("document is not active")
    if document.archived:
        reasons.append("document is archived")

    current_versions = [
        version for version in document.versions if version.is_current
    ]
    if not current_versions:
        reasons.append("current version does not exist")
    elif len(current_versions) > 1:
        reasons.append("document has multiple current versions")
    else:
        current = current_versions[0]
        if not current.is_current:
            reasons.append("current version is not marked current")
        if not current.checksum.strip():
            reasons.append("current version checksum does not exist")
        if not current.files and not current.stored_files:
            reasons.append("current version has no file metadata")

    if reasons:
        raise ResourceValidationError(
            "Document is not eligible for ingestion: " + "; ".join(reasons)
        )
    return True


__all__ = [
    "add_identifier",
    "archive_document",
    "create_relationship",
    "get_document",
    "list_import_batches",
    "register_document",
    "register_file_metadata",
    "register_version",
    "remove_identifier",
    "restore_document",
    "search_documents",
    "set_current_version",
    "update_document",
    "validate_ingestion_eligibility",
]
