from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import (
    LegacySourceCreate,
    LegacySourceResponse,
    LegacySourceUpdate,
    PaginatedResponse,
)
from ..services import sources as source_service
from .dependencies import get_db


router = APIRouter(prefix="/sources", tags=["sources"])


@router.post(
    "",
    response_model=LegacySourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source(request: LegacySourceCreate, db: Session = Depends(get_db)):
    return source_service.create_source(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[LegacySourceResponse])
def list_sources(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    source_type: str | None = Query(default=None, min_length=1),
    author: str | None = Query(default=None, min_length=1),
    q: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    items, total = source_service.list_sources(
        db,
        skip=skip,
        limit=limit,
        source_type=source_type,
        author=author,
        q=q,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{source_id}", response_model=LegacySourceResponse)
def get_source(
    source_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return source_service.get_source(db, source_id)


@router.patch("/{source_id}", response_model=LegacySourceResponse)
def update_source(
    request: LegacySourceUpdate,
    source_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return source_service.update_source(
        db,
        source_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    source_service.delete_source(db, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
