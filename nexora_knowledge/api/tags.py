from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import PaginatedResponse, TagCreate, TagResponse, TagUpdate
from ..services import tags as tag_service
from .dependencies import get_db


router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(request: TagCreate, db: Session = Depends(get_db)):
    return tag_service.create_tag(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[TagResponse])
def list_tags(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    items, total = tag_service.list_tags(db, skip=skip, limit=limit, q=q)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{tag_id}", response_model=TagResponse)
def get_tag(tag_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return tag_service.get_tag(db, tag_id)


@router.patch("/{tag_id}", response_model=TagResponse)
def update_tag(
    request: TagUpdate,
    tag_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return tag_service.update_tag(
        db,
        tag_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    tag_service.delete_tag(db, tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
