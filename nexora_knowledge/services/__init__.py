import re
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from ..models import KnowledgeChunk, KnowledgeDocument
from ..schemas import SearchResult
from .exceptions import (
    AcademyInputError,
    AuthenticationRequiredError,
    AuthorizationDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
    ServiceError,
)
from . import (
    authorization,
    chunking_pipeline_service,
    chunking_service,
    document_service,
    grading,
    ingestion_service,
    learning,
    parser_service,
    parse_result_service,
    parser_pipeline_service,
    source_service,
    storage_service,
)

def _tokens(query: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9_'-]+", query) if len(t) >= 2]

def search_knowledge(db: Session, query: str, category: str | None = None, limit: int = 10) -> list[SearchResult]:
    tokens = _tokens(query)
    if not tokens:
        return []
    conditions = [func.lower(KnowledgeChunk.content).like(f"%{token}%") for token in tokens]
    stmt = select(KnowledgeChunk, KnowledgeDocument).join(
        KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id
    ).where(or_(*conditions))
    if category:
        stmt = stmt.where(KnowledgeChunk.category == category)
    rows = db.execute(stmt.limit(max(limit * 5, limit))).all()
    results = []
    for chunk, document in rows:
        lowered = chunk.content.lower()
        score = sum(lowered.count(token) for token in tokens)
        if score:
            results.append(SearchResult(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                category=chunk.category,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=score,
            ))
    results.sort(key=lambda item: (-item.score, item.document_id, item.chunk_index))
    return results[:limit]

def knowledge_stats(db: Session) -> dict:
    documents = db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0
    chunks = db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0
    categories = dict(db.execute(
        select(KnowledgeChunk.category, func.count())
        .group_by(KnowledgeChunk.category)
        .order_by(KnowledgeChunk.category)
    ).all())
    return {"documents": documents, "chunks": chunks, "categories": categories}


__all__ = [
    "ResourceConflictError",
    "ResourceNotFoundError",
    "ResourceValidationError",
    "ServiceError",
    "AcademyInputError",
    "AuthenticationRequiredError",
    "AuthorizationDeniedError",
    "knowledge_stats",
    "search_knowledge",
    "learning",
    "parser_service",
    "parser_pipeline_service",
    "parse_result_service",
    "authorization",
    "chunking_pipeline_service",
    "chunking_service",
    "document_service",
    "ingestion_service",
    "grading",
    "source_service",
    "storage_service",
]

# Rich-knowledge service modules are imported explicitly by callers so the
# existing lightweight Pack 1 search API retains its current import behavior.
