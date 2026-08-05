from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..ingest import ingest_document
from ..schemas import IngestRequest, SearchResult
from ..services import knowledge_stats, search_knowledge
from .dependencies import get_db


router = APIRouter()


@router.get("/health")
def health():
    return {"status":"ok","service":"nexora-knowledge","version":"2.0.0"}


@router.post("/ingest")
def ingest(request: IngestRequest, db: Session = Depends(get_db)):
    try:
        document = ingest_document(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"document_id":document.id,"title":document.title,
            "category":document.category,"chunks":len(document.chunks)}


@router.get("/search", response_model=list[SearchResult])
def search(q: str = Query(min_length=2), category: str | None = None,
           limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)):
    return search_knowledge(db, q, category, limit)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return knowledge_stats(db)
