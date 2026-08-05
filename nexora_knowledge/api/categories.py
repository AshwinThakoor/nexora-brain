from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    PaginatedResponse,
)
from ..services import categories as category_service
from .dependencies import get_db


router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    request: CategoryCreate,
    db: Session = Depends(get_db),
):
    return category_service.create_category(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[CategoryResponse])
def list_categories(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    parent_id: int | None = Query(default=None, gt=0),
    name: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    items, total = category_service.list_categories(
        db,
        skip=skip,
        limit=limit,
        parent_id=parent_id,
        name=name,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return category_service.get_category(db, category_id)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    request: CategoryUpdate,
    category_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return category_service.update_category(
        db,
        category_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    category_service.delete_category(db, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
