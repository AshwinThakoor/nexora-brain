from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import (
    ClaimCreate,
    ClaimDetail,
    ClaimResponse,
    ClaimUpdate,
    PaginatedResponse,
)
from ..services import claims as claim_service
from .dependencies import get_db


router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=ClaimDetail, status_code=status.HTTP_201_CREATED)
def create_claim(request: ClaimCreate, db: Session = Depends(get_db)):
    return claim_service.create_claim(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[ClaimResponse])
def list_claims(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    concept_id: int | None = Query(default=None, gt=0),
    claim_type: str | None = Query(default=None, min_length=1),
    status_filter: str | None = Query(default=None, alias="status", min_length=1),
    min_confidence_score: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
    ),
    q: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    items, total = claim_service.list_claims(
        db,
        skip=skip,
        limit=limit,
        concept_id=concept_id,
        claim_type=claim_type,
        status=status_filter,
        min_confidence_score=min_confidence_score,
        q=q,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(
    claim_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return claim_service.get_claim(db, claim_id)


@router.patch("/{claim_id}", response_model=ClaimDetail)
def update_claim(
    request: ClaimUpdate,
    claim_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return claim_service.update_claim(
        db,
        claim_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_claim(
    claim_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    claim_service.delete_claim(db, claim_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
