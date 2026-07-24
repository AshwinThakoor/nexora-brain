from hashlib import sha256
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from .chunker import chunk_text
from .classifier import classify_text
from .cleaner import clean_text
from .config import get_settings
from .models import KnowledgeChunk, KnowledgeDocument
from .parsers import parse_document
from .schemas import IngestRequest

def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def ingest_document(db: Session, request: IngestRequest) -> KnowledgeDocument:
    settings = get_settings()
    path = Path(request.file_path).resolve()
    digest = file_sha256(path)
    existing = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.sha256 == digest))
    if existing:
        raise ValueError(f"This exact file was already ingested as document_id={existing.id}")
    text = clean_text(parse_document(str(path)))
    if len(text) < 20:
        raise ValueError("No usable text was extracted from the document.")
    pieces = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not pieces:
        raise ValueError("The document produced no chunks.")
    document = KnowledgeDocument(
        title=request.title or path.stem,
        author=request.author,
        publisher=request.publisher,
        source_name=request.source_name,
        source_url=request.source_url,
        file_path=str(path),
        file_type=path.suffix.lower().lstrip("."),
        sha256=digest,
        category=classify_text(text),
        license_status=request.license_status,
        license_notes=request.license_notes,
        commercial_use_allowed=request.commercial_use_allowed,
        quality_score=request.quality_score,
    )
    for index, content in enumerate(pieces):
        document.chunks.append(KnowledgeChunk(
            chunk_index=index,
            category=classify_text(content),
            content=content,
            word_count=len(content.split()),
        ))
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
