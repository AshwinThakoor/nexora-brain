from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..models import SourceType, TrustLevel
from ..schemas import (
    SourceCreate,
    SourceRead,
    SourceSearch,
    SourceUpdate,
)
from ..services import source_service
from ..services.authorization import (
    Principal,
    require_source_admin,
    require_source_reader,
)
from .dependencies import get_current_principal, get_db


router = APIRouter(
    prefix="/api/v1/sources",
    tags=["source-registry"],
)

SortField = Literal[
    "id",
    "slug",
    "title",
    "source_type",
    "language",
    "trust_level",
    "publication_date",
    "created_at",
    "updated_at",
]
SortOrder = Literal["asc", "desc"]


def _search(
    db: Session,
    *,
    q: str | None,
    source_type: SourceType | None,
    organization: str | None,
    language: str | None,
    trust: TrustLevel | None,
    tag: str | None,
    active: bool | None,
    archived: bool | None,
    offset: int,
    limit: int,
    sort_by: SortField,
    sort_order: SortOrder,
) -> SourceSearch:
    items, total = source_service.search_sources(
        db,
        q=q,
        source_type=source_type,
        organization=organization,
        language=language,
        trust=trust,
        tag=tag,
        active=active,
        archived=archived,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return SourceSearch(
        items=items,
        total=total,
        offset=offset,
        skip=offset,
        limit=limit,
    )


@router.post(
    "",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    request: SourceCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_source_admin(principal)
    return source_service.create_source(db, request.model_dump())


@router.get("", response_model=SourceSearch)
def list_sources(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    source_type: Annotated[
        SourceType | None,
        Query(alias="type"),
    ] = None,
    organization: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    language: Annotated[
        str | None,
        Query(min_length=2, max_length=16),
    ] = None,
    trust: TrustLevel | None = None,
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
    require_source_reader(principal)
    return _search(
        db,
        q=None,
        source_type=source_type,
        organization=organization,
        language=language,
        trust=trust,
        tag=tag,
        active=active,
        archived=archived,
        offset=skip if skip is not None else offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/search", response_model=SourceSearch)
def search_sources(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    source_type: Annotated[
        SourceType | None,
        Query(alias="type"),
    ] = None,
    organization: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    language: Annotated[
        str | None,
        Query(min_length=2, max_length=16),
    ] = None,
    trust: TrustLevel | None = None,
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
    require_source_reader(principal)
    return _search(
        db,
        q=q,
        source_type=source_type,
        organization=organization,
        language=language,
        trust=trust,
        tag=tag,
        active=active,
        archived=archived,
        offset=skip if skip is not None else offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{source_id}", response_model=SourceRead)
def get_source(
    source_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_source_reader(principal)
    return source_service.get_source(db, source_id)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    request: SourceUpdate,
    source_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_source_admin(principal)
    return source_service.update_source(
        db,
        source_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_source(
    source_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    require_source_admin(principal)
    source_service.archive_source(db, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
