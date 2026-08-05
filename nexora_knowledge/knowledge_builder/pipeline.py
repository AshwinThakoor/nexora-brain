from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from ..cleaner import clean_text
from ..database import SessionLocal
from ..db_management import initialize_development_database
from .extractor import KnowledgeExtractor
from .utils import KnowledgeBuildResult, Timer


def build_knowledge(
    document_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    db: Session | None = None,
) -> KnowledgeBuildResult:
    timer = Timer().start()
    result = KnowledgeBuildResult()
    duplicates_skipped = 0
    owned_session = db is None

    try:
        if not isinstance(document_text, str):
            raise TypeError("document_text must be a string")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")

        normalized_text = clean_text(document_text)
        if len(normalized_text) < 20:
            result.errors.append(
                "No usable text was supplied to the knowledge builder"
            )
            return _finalize(result, duplicates_skipped, timer)

        if owned_session:
            initialize_development_database()
            db = SessionLocal()
        if db is None:
            raise RuntimeError("A database session could not be created")

        extractor = KnowledgeExtractor(db)
        result, duplicates_skipped = extractor.extract(
            normalized_text,
            dict(metadata or {}),
        )
    except Exception as exc:
        if db is not None:
            db.rollback()
        result.errors.append(f"Knowledge build failed: {exc}")
    finally:
        if owned_session and db is not None:
            db.close()

    return _finalize(result, duplicates_skipped, timer)


def _finalize(
    result: KnowledgeBuildResult,
    duplicates_skipped: int,
    timer: Timer,
) -> KnowledgeBuildResult:
    result.duration_ms = timer.elapsed_ms
    result.statistics = {
        "categories_created": len(result.created_categories),
        "concepts_created": len(result.created_concepts),
        "claims_created": len(result.created_claims),
        "relationships_created": len(result.created_relationships),
        "tags_created": len(result.created_tags),
        "sources_created": len(result.created_sources),
        "duplicates_skipped": duplicates_skipped,
        "processing_time_ms": result.duration_ms,
    }
    return result


__all__ = ["KnowledgeBuildResult", "build_knowledge"]
