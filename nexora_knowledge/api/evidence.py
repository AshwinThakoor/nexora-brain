from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..schemas import (
    EvidenceCreate,
    EvidenceResponse,
    EvidenceUpdate,
    PaginatedResponse,
)
from ..services import evidence as evidence_service
from .dependencies import get_db


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post(
    "",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence(
    request: EvidenceCreate,
    db: Session = Depends(get_db),
):
    return evidence_service.create_evidence(db, request.model_dump())


@router.get("", response_model=PaginatedResponse[EvidenceResponse])
def list_evidence(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    claim_id: int | None = Query(default=None, gt=0),
    source_id: int | None = Query(default=None, gt=0),
    evidence_type: str | None = Query(default=None, min_length=1),
    strength: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    items, total = evidence_service.list_evidence(
        db,
        skip=skip,
        limit=limit,
        claim_id=claim_id,
        source_id=source_id,
        evidence_type=evidence_type,
        strength=strength,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return evidence_service.get_evidence(db, evidence_id)


@router.patch("/{evidence_id}", response_model=EvidenceResponse)
def update_evidence(
    request: EvidenceUpdate,
    evidence_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return evidence_service.update_evidence(
        db,
        evidence_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    evidence_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    evidence_service.delete_evidence(db, evidence_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
