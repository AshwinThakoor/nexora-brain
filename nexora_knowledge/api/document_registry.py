from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..models import DocumentStatus, DocumentType, ProcessingStatus
from ..schemas import (
    DocumentCreate,
    DocumentIdentifierCreate,
    DocumentIdentifierRead,
    DocumentRead,
    DocumentRelationshipCreate,
    DocumentRelationshipRead,
    DocumentSearch,
    DocumentUpdate,
    DocumentVersionCreate,
    DocumentVersionRead,
    ImportBatchSearch,
)
from ..services import document_service
from ..services.authorization import (
    Principal,
    require_document_admin,
    require_document_reader,
)
from .dependencies import get_current_principal, get_db


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["document-registry"],
)
import_batch_router = APIRouter(
    prefix="/api/v1/import-batches",
    tags=["document-registry"],
)

SortField = Literal[
    "id",
    "slug",
    "source_id",
    "title",
    "document_type",
    "language",
    "publication_date",
    "publication_year",
    "status",
    "created_at",
    "updated_at",
]
SortOrder = Literal["asc", "desc"]


def _search(
    db: Session,
    *,
    q: str | None,
    title: str | None,
    subtitle: str | None,
    author: str | None,
    language: str | None,
    source: str | None,
    document_status: DocumentStatus | None,
    document_type: DocumentType | None,
    publication_year: int | None,
    identifier: str | None,
    tag: str | None,
    active: bool | None,
    archived: bool | None,
    offset: int,
    limit: int,
    sort_by: SortField,
    sort_order: SortOrder,
) -> DocumentSearch:
    items, total = document_service.search_documents(
        db,
        q=q,
        title=title,
        subtitle=subtitle,
        author=author,
        language=language,
        source=source,
        status=document_status,
        document_type=document_type,
        publication_year=publication_year,
        identifier=identifier,
        tag=tag,
        active=active,
        archived=archived,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return DocumentSearch(
        items=items,
        total=total,
        offset=offset,
        skip=offset,
        limit=limit,
    )


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def register_document(
    request: DocumentCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_document_admin(principal)
    return document_service.register_document(db, request.model_dump())


@router.get("", response_model=DocumentSearch)
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    title: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    subtitle: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    author: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    language: Annotated[
        str | None,
        Query(min_length=2, max_length=16),
    ] = None,
    source: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    document_status: Annotated[
        DocumentStatus | None,
        Query(alias="status"),
    ] = None,
    document_type: Annotated[
        DocumentType | None,
        Query(alias="type"),
    ] = None,
    publication_year: Annotated[
        int | None,
        Query(ge=1000, le=9999),
    ] = None,
    identifier: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    tag: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    active: bool | None = None,
    archived: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: SortField = "created_at",
    sort_order: SortOrder = "desc",
):
    require_document_reader(principal)
    return _search(
        db,
        q=None,
        title=title,
        subtitle=subtitle,
        author=author,
        language=language,
        source=source,
        document_status=document_status,
        document_type=document_type,
        publication_year=publication_year,
        identifier=identifier,
        tag=tag,
        active=active,
        archived=archived,
        offset=skip if skip is not None else offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/search", response_model=DocumentSearch)
def search_documents(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    title: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    subtitle: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    author: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    language: Annotated[
        str | None,
        Query(min_length=2, max_length=16),
    ] = None,
    source: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    document_status: Annotated[
        DocumentStatus | None,
        Query(alias="status"),
    ] = None,
    document_type: Annotated[
        DocumentType | None,
        Query(alias="type"),
    ] = None,
    publication_year: Annotated[
        int | None,
        Query(ge=1000, le=9999),
    ] = None,
    identifier: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    tag: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    active: bool | None = None,
    archived: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: SortField = "created_at",
    sort_order: SortOrder = "desc",
):
    require_document_reader(principal)
    return _search(
        db,
        q=q,
        title=title,
        subtitle=subtitle,
        author=author,
        language=language,
        source=source,
        document_status=document_status,
        document_type=document_type,
        publication_year=publication_year,
        identifier=identifier,
        tag=tag,
        active=active,
        archived=archived,
        offset=skip if skip is not None else offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_document_reader(principal)
    return document_service.get_document(db, document_id)


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(
    request: DocumentUpdate,
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_document_admin(principal)
    return document_service.update_document(
        db,
        document_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def archive_document(
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    require_document_admin(principal)
    document_service.archive_document(db, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def register_version(
    request: DocumentVersionCreate,
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_document_admin(principal)
    return document_service.register_version(
        db,
        document_id,
        request.model_dump(),
    )


@router.post(
    "/{document_id}/identifiers",
    response_model=DocumentIdentifierRead,
    status_code=status.HTTP_201_CREATED,
)
def add_identifier(
    request: DocumentIdentifierCreate,
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_document_admin(principal)
    return document_service.add_identifier(
        db,
        document_id,
        request.model_dump(),
    )


@router.post(
    "/{document_id}/relationships",
    response_model=DocumentRelationshipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    request: DocumentRelationshipCreate,
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_document_admin(principal)
    return document_service.create_relationship(
        db,
        document_id,
        request.model_dump(),
    )


@import_batch_router.get("", response_model=ImportBatchSearch)
def list_import_batches(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    batch_status: Annotated[
        ProcessingStatus | None,
        Query(alias="status"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    require_document_reader(principal)
    resolved_offset = skip if skip is not None else offset
    items, total = document_service.list_import_batches(
        db,
        status=batch_status,
        offset=resolved_offset,
        limit=limit,
    )
    return ImportBatchSearch(
        items=items,
        total=total,
        offset=resolved_offset,
        skip=resolved_offset,
        limit=limit,
    )


__all__ = ["import_batch_router", "router"]
