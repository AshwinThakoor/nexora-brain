from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import (
    ClaimResponse,
    ConceptCreate,
    ConceptDetail,
    ConceptResponse,
    PaginatedResponse,
    RelationshipResponse,
)
from ..schemas.concept import ConceptUpdate
from ..services import concepts as concept_service
from .dependencies import get_db


router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.post("", response_model=ConceptDetail, status_code=status.HTTP_201_CREATED)
def create_concept(
    request: ConceptCreate,
    db: Session = Depends(get_db),
):
    return concept_service.create_concept(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[ConceptResponse])
def list_concepts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    category_id: int | None = Query(default=None, gt=0),
    difficulty: str | None = Query(default=None, min_length=1),
    status_filter: str | None = Query(default=None, alias="status", min_length=1),
    tag_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    items, total = concept_service.list_concepts(
        db,
        skip=skip,
        limit=limit,
        category_id=category_id,
        difficulty=difficulty,
        status=status_filter,
        tag_id=tag_id,
        q=q,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{concept_id}", response_model=ConceptDetail)
def get_concept(
    concept_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return concept_service.get_concept(db, concept_id)


@router.patch("/{concept_id}", response_model=ConceptDetail)
def update_concept(
    request: ConceptUpdate,
    concept_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return concept_service.update_concept(
        db,
        concept_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_concept(
    concept_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    concept_service.delete_concept(db, concept_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{concept_id}/tags/{tag_id}", response_model=ConceptDetail)
def attach_tag(
    concept_id: int = Path(gt=0),
    tag_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return concept_service.attach_tag(db, concept_id, tag_id)


@router.delete("/{concept_id}/tags/{tag_id}", response_model=ConceptDetail)
def remove_tag(
    concept_id: int = Path(gt=0),
    tag_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return concept_service.remove_tag(db, concept_id, tag_id)


@router.get("/{concept_id}/claims", response_model=list[ClaimResponse])
def get_concept_claims(
    concept_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return concept_service.get_concept_claims(db, concept_id)


@router.get(
    "/{concept_id}/relationships",
    response_model=list[RelationshipResponse],
)
def get_concept_relationships(
    concept_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return concept_service.get_concept_relationships(db, concept_id)
