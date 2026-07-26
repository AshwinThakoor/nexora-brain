from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import SessionLocal, init_database
from ..ingest import ingest_document
from ..schemas import IngestRequest, SearchResult
from ..services import knowledge_stats, search_knowledge

app = FastAPI(title="NEXORA Knowledge Engine", version="2.0.0")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup():
    init_database()

@app.get("/health")
def health():
    return {"status":"ok","service":"nexora-knowledge","version":"2.0.0"}

@app.post("/ingest")
def ingest(request: IngestRequest, db: Session = Depends(get_db)):
    try:
        document = ingest_document(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"document_id":document.id,"title":document.title,
            "category":document.category,"chunks":len(document.chunks)}

@app.get("/search", response_model=list[SearchResult])
def search(q: str = Query(min_length=2), category: str | None = None,
           limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)):
    return search_knowledge(db, q, category, limit)

@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    return knowledge_stats(db)
