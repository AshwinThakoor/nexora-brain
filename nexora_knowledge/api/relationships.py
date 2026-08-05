from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import (
    PaginatedResponse,
    RelationshipCreate,
    RelationshipResponse,
    RelationshipUpdate,
)
from ..services import relationships as relationship_service
from .dependencies import get_db


router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.post(
    "",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    request: RelationshipCreate,
    db: Session = Depends(get_db),
):
    return relationship_service.create_relationship(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[RelationshipResponse])
def list_relationships(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    source_concept_id: int | None = Query(default=None, gt=0),
    target_concept_id: int | None = Query(default=None, gt=0),
    relationship_type: str | None = Query(default=None, min_length=1),
    min_confidence_score: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
    ),
    db: Session = Depends(get_db),
):
    items, total = relationship_service.list_relationships(
        db,
        skip=skip,
        limit=limit,
        source_concept_id=source_concept_id,
        target_concept_id=target_concept_id,
        relationship_type=relationship_type,
        min_confidence_score=min_confidence_score,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{relationship_id}", response_model=RelationshipResponse)
def get_relationship(
    relationship_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return relationship_service.get_relationship(db, relationship_id)


@router.patch("/{relationship_id}", response_model=RelationshipResponse)
def update_relationship(
    request: RelationshipUpdate,
    relationship_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return relationship_service.update_relationship(
        db,
        relationship_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    relationship_service.delete_relationship(db, relationship_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
