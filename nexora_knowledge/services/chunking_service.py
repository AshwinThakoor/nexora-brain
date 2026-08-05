from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import asc, cast, desc, exists, func, select, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..chunking.models import ChunkCandidate, ChunkConfiguration
from ..models import (
    ChunkRelationship,
    ChunkSet,
    ChunkSetStatus,
    ChunkSourceSpan,
    ChunkingArtifact,
    ChunkingArtifactType,
    ChunkingExecution,
    ChunkingExecutionStatus,
    KnowledgeChunk,
    ParseResult,
)
from ..models.common import utc_now
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


_SET_SORT_COLUMNS = {
    "id": ChunkSet.id,
    "parse_result_id": ChunkSet.parse_result_id,
    "document_version_id": ChunkSet.document_version_id,
    "stored_file_id": ChunkSet.stored_file_id,
    "strategy_name": ChunkSet.strategy_name,
    "strategy_version": ChunkSet.strategy_version,
    "status": ChunkSet.status,
    "configuration_hash": ChunkSet.configuration_hash,
    "canonical_content_hash": ChunkSet.canonical_content_hash,
    "content_hash": ChunkSet.content_hash,
    "created_at": ChunkSet.created_at,
    "completed_at": ChunkSet.completed_at,
}
_CHUNK_SORT_COLUMNS = {
    "id": KnowledgeChunk.id,
    "ordinal": KnowledgeChunk.ordinal,
    "content_type": KnowledgeChunk.content_type,
    "language": KnowledgeChunk.language,
    "character_count": KnowledgeChunk.character_count,
    "word_count": KnowledgeChunk.word_count,
    "created_at": KnowledgeChunk.created_at,
}


def _set_query():
    return (
        select(ChunkSet)
        .options(
            selectinload(ChunkSet.executions),
            selectinload(ChunkSet.artifacts),
            selectinload(ChunkSet.relationships),
            selectinload(ChunkSet.chunks).selectinload(
                KnowledgeChunk.source_spans
            ),
        )
        .execution_options(populate_existing=True)
    )


def _commit(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(message) from exc


def serialize_chunk_configuration(
    configuration: ChunkConfiguration | Mapping[str, Any],
) -> str:
    try:
        config = (
            configuration
            if isinstance(configuration, ChunkConfiguration)
            else ChunkConfiguration.model_validate(dict(configuration))
        )
        return config.canonical_json()
    except (TypeError, ValueError) as exc:
        raise ResourceValidationError(
            "Chunk configuration is invalid"
        ) from exc


def calculate_configuration_hash(
    configuration: ChunkConfiguration | Mapping[str, Any] | str,
) -> str:
    if isinstance(configuration, str):
        try:
            payload = json.loads(configuration)
        except json.JSONDecodeError as exc:
            raise ResourceValidationError(
                "Chunk configuration JSON is invalid"
            ) from exc
        serialized = serialize_chunk_configuration(payload)
    else:
        serialized = serialize_chunk_configuration(configuration)
    return sha256(serialized.encode("utf-8")).hexdigest()


def calculate_chunk_content_hash(
    value: ChunkCandidate | KnowledgeChunk | str,
    *,
    content_type: str | None = None,
    heading_context: Sequence[str] | None = None,
) -> str:
    if isinstance(value, ChunkCandidate):
        text = value.text
        resolved_type = value.content_type.value
        context = value.heading_context
    elif isinstance(value, KnowledgeChunk):
        text = value.text or value.content
        resolved_type = value.content_type or content_type or "text"
        raw_context = value.heading_context_json or []
        context = raw_context if isinstance(raw_context, list) else []
    else:
        text = value
        resolved_type = content_type or "text"
        context = list(heading_context or [])
    payload = {
        "content_type": resolved_type,
        "heading_context": context,
        "text": text,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def calculate_chunk_set_content_hash(
    chunks: Iterable[ChunkCandidate | KnowledgeChunk | str],
) -> str:
    hashes = []
    for item in chunks:
        if isinstance(item, str) and len(item) == 64:
            hashes.append(item)
        else:
            hashes.append(calculate_chunk_content_hash(item))
    serialized = json.dumps(
        hashes,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def create_or_get_chunk_set(
    db: Session,
    parse_result_id: int,
    configuration: ChunkConfiguration | Mapping[str, Any],
    *,
    canonical_content_hash: str | None = None,
) -> ChunkSet:
    parse_result = db.get(ParseResult, parse_result_id)
    if parse_result is None:
        raise ResourceNotFoundError("Parse result", parse_result_id)
    config = (
        configuration
        if isinstance(configuration, ChunkConfiguration)
        else ChunkConfiguration.model_validate(dict(configuration))
    )
    serialized = serialize_chunk_configuration(config)
    config_hash = calculate_configuration_hash(serialized)
    canonical_hash = (
        canonical_content_hash or parse_result.content_hash or ""
    ).strip().casefold()
    if len(canonical_hash) != 64:
        raise ResourceValidationError(
            "Parse result canonical content hash is unavailable"
        )
    identity = (
        ChunkSet.parse_result_id == parse_result.id,
        ChunkSet.canonical_content_hash == canonical_hash,
        ChunkSet.strategy_name == config.strategy_name,
        ChunkSet.strategy_version == config.strategy_version,
        ChunkSet.configuration_hash == config_hash,
    )
    existing = db.scalar(_set_query().where(*identity))
    if existing is not None:
        return existing
    chunk_set = ChunkSet(
        parse_result_id=parse_result.id,
        document_version_id=parse_result.document_version_id,
        stored_file_id=parse_result.stored_file_id,
        strategy_name=config.strategy_name,
        strategy_version=config.strategy_version,
        configuration_json=serialized,
        configuration_hash=config_hash,
        canonical_content_hash=canonical_hash,
        status=ChunkSetStatus.PENDING.value,
        started_at=utc_now(),
    )
    db.add(chunk_set)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(_set_query().where(*identity))
        if concurrent is not None:
            return concurrent
        raise ResourceConflictError("Chunk set identity already exists")
    return get_chunk_set(db, chunk_set.id)


def begin_chunking_execution(
    db: Session,
    chunk_set_id: int,
    *,
    node_name: str | None = None,
) -> ChunkingExecution:
    chunk_set = db.scalar(
        select(ChunkSet)
        .where(ChunkSet.id == chunk_set_id)
        .with_for_update()
    )
    if chunk_set is None:
        raise ResourceNotFoundError("Chunk set", chunk_set_id)
    if chunk_set.status in {
        ChunkSetStatus.SUCCEEDED.value,
        ChunkSetStatus.INVALIDATED.value,
    }:
        raise ResourceConflictError(
            "Immutable chunk set cannot start another execution"
        )
    running = db.scalar(
        select(ChunkingExecution).where(
            ChunkingExecution.chunk_set_id == chunk_set.id,
            ChunkingExecution.status
            == ChunkingExecutionStatus.RUNNING.value,
            ChunkingExecution.finished_at.is_(None),
        )
    )
    if running is not None:
        raise ResourceConflictError(
            "Chunk set already has a running execution"
        )
    attempt = db.scalar(
        select(func.max(ChunkingExecution.attempt_number)).where(
            ChunkingExecution.chunk_set_id == chunk_set.id
        )
    ) or 0
    execution = ChunkingExecution(
        chunk_set_id=chunk_set.id,
        attempt_number=attempt + 1,
        status=ChunkingExecutionStatus.RUNNING.value,
        started_at=utc_now(),
        strategy_name=chunk_set.strategy_name,
        strategy_version=chunk_set.strategy_version,
        node_name=(node_name.strip() or None) if node_name else None,
    )
    db.add(execution)
    chunk_set.status = ChunkSetStatus.CHUNKING.value
    chunk_set.completed_at = None
    _commit(db, "Chunking execution could not be started")
    db.refresh(execution)
    return execution


def complete_chunking_execution(
    db: Session,
    execution_id: int,
    *,
    content_hash: str | None = None,
) -> ChunkSet:
    execution = db.scalar(
        select(ChunkingExecution)
        .where(ChunkingExecution.id == execution_id)
        .with_for_update()
    )
    if execution is None:
        raise ResourceNotFoundError("Chunking execution", execution_id)
    if execution.status != ChunkingExecutionStatus.RUNNING.value:
        raise ResourceConflictError("Chunking execution is not running")
    chunk_set = db.scalar(
        select(ChunkSet)
        .where(ChunkSet.id == execution.chunk_set_id)
        .with_for_update()
    )
    if chunk_set is None:
        raise ResourceNotFoundError("Chunk set", execution.chunk_set_id)
    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.chunk_set_id == chunk_set.id)
            .order_by(KnowledgeChunk.ordinal, KnowledgeChunk.id)
        )
    )
    if not chunks:
        raise ResourceValidationError(
            "A successful chunk set must contain at least one chunk"
        )
    expected_ordinals = list(range(len(chunks)))
    if [chunk.ordinal for chunk in chunks] != expected_ordinals:
        raise ResourceValidationError("Chunk ordinals are not contiguous")
    resolved_hash = content_hash or calculate_chunk_set_content_hash(chunks)
    now = utc_now()
    execution.status = ChunkingExecutionStatus.SUCCEEDED.value
    execution.finished_at = now
    execution.duration_ms = _duration_ms(execution.started_at, now)
    chunk_set.chunk_count = len(chunks)
    chunk_set.total_character_count = sum(
        chunk.character_count or 0 for chunk in chunks
    )
    chunk_set.total_word_count = sum(chunk.word_count for chunk in chunks)
    chunk_set.content_hash = resolved_hash
    chunk_set.status = ChunkSetStatus.SUCCEEDED.value
    chunk_set.completed_at = now
    _commit(db, "Chunking execution could not be completed")
    return get_chunk_set(db, chunk_set.id)


def fail_chunking_execution(
    db: Session,
    execution_id: int,
    *,
    error_code: str,
    error_message: str,
) -> ChunkSet:
    execution = db.scalar(
        select(ChunkingExecution)
        .where(ChunkingExecution.id == execution_id)
        .with_for_update()
    )
    if execution is None:
        raise ResourceNotFoundError("Chunking execution", execution_id)
    if execution.status != ChunkingExecutionStatus.RUNNING.value:
        raise ResourceConflictError("Chunking execution is not running")
    chunk_set = db.scalar(
        select(ChunkSet)
        .where(ChunkSet.id == execution.chunk_set_id)
        .with_for_update()
    )
    if chunk_set is None:
        raise ResourceNotFoundError("Chunk set", execution.chunk_set_id)
    now = utc_now()
    execution.status = ChunkingExecutionStatus.FAILED.value
    execution.finished_at = now
    execution.duration_ms = _duration_ms(execution.started_at, now)
    execution.error_code = _safe_text(error_code, 100)
    execution.error_message = _safe_text(error_message, 2000)
    chunk_set.status = ChunkSetStatus.FAILED.value
    chunk_set.completed_at = now
    _commit(db, "Chunking failure history could not be persisted")
    return get_chunk_set(db, chunk_set.id)


def invalidate_chunk_set(db: Session, chunk_set_id: int) -> ChunkSet:
    chunk_set = db.scalar(
        select(ChunkSet)
        .where(ChunkSet.id == chunk_set_id)
        .with_for_update()
    )
    if chunk_set is None:
        raise ResourceNotFoundError("Chunk set", chunk_set_id)
    if chunk_set.status == ChunkSetStatus.INVALIDATED.value:
        return get_chunk_set(db, chunk_set.id)
    if chunk_set.status != ChunkSetStatus.SUCCEEDED.value:
        raise ResourceConflictError(
            "Only successful chunk sets can be invalidated"
        )
    chunk_set.status = ChunkSetStatus.INVALIDATED.value
    _commit(db, "Chunk set could not be invalidated")
    return get_chunk_set(db, chunk_set.id)


def get_chunk_set(db: Session, chunk_set_id: int) -> ChunkSet:
    chunk_set = db.scalar(
        _set_query().where(ChunkSet.id == chunk_set_id)
    )
    if chunk_set is None:
        raise ResourceNotFoundError("Chunk set", chunk_set_id)
    return chunk_set


def get_current_chunk_set(
    db: Session,
    parse_result_id: int,
) -> ChunkSet | None:
    return db.scalar(
        _set_query()
        .where(
            ChunkSet.parse_result_id == parse_result_id,
            ChunkSet.status == ChunkSetStatus.SUCCEEDED.value,
        )
        .order_by(
            desc(ChunkSet.completed_at),
            desc(ChunkSet.id),
        )
        .limit(1)
    )


def list_chunk_sets(
    db: Session,
    *,
    parse_result_id: int | None = None,
    document_version_id: int | None = None,
    stored_file_id: int | None = None,
    strategy_name: str | None = None,
    strategy_version: str | None = None,
    status: str | None = None,
    configuration_hash: str | None = None,
    canonical_content_hash: str | None = None,
    content_hash: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    offset: int = 0,
    skip: int | None = None,
    limit: int = 50,
) -> tuple[list[ChunkSet], int]:
    conditions = []
    exact = {
        ChunkSet.parse_result_id: parse_result_id,
        ChunkSet.document_version_id: document_version_id,
        ChunkSet.stored_file_id: stored_file_id,
        ChunkSet.strategy_name: strategy_name,
        ChunkSet.strategy_version: strategy_version,
        ChunkSet.status: status,
        ChunkSet.configuration_hash: configuration_hash,
        ChunkSet.canonical_content_hash: canonical_content_hash,
        ChunkSet.content_hash: content_hash,
    }
    for column, value in exact.items():
        if value is not None:
            conditions.append(column == value)
    if created_from is not None:
        conditions.append(ChunkSet.created_at >= created_from)
    if created_to is not None:
        conditions.append(ChunkSet.created_at <= created_to)
    effective_offset = offset if skip is None else skip
    if effective_offset < 0 or not 1 <= limit <= 200:
        raise ResourceValidationError("Chunk set pagination is invalid")
    column = _SET_SORT_COLUMNS.get(sort_by)
    if column is None or sort_order.casefold() not in {"asc", "desc"}:
        raise ResourceValidationError("Chunk set sorting is invalid")
    order = asc if sort_order.casefold() == "asc" else desc
    total = db.scalar(
        select(func.count()).select_from(ChunkSet).where(*conditions)
    ) or 0
    items = list(
        db.scalars(
            _set_query()
            .where(*conditions)
            .order_by(order(column), order(ChunkSet.id))
            .offset(effective_offset)
            .limit(limit)
        )
    )
    return items, total


def get_chunking_history(
    db: Session,
    chunk_set_id: int,
) -> list[ChunkingExecution]:
    get_chunk_set(db, chunk_set_id)
    return list(
        db.scalars(
            select(ChunkingExecution)
            .where(ChunkingExecution.chunk_set_id == chunk_set_id)
            .order_by(
                ChunkingExecution.attempt_number,
                ChunkingExecution.id,
            )
        )
    )


def list_chunks(
    db: Session,
    *,
    chunk_set_id: int | None = None,
    content_type: str | None = None,
    language: str | None = None,
    content_hash: str | None = None,
    minimum_character_count: int | None = None,
    maximum_character_count: int | None = None,
    page_number: int | None = None,
    section_path: str | None = None,
    text_query: str | None = None,
    sort_by: str = "ordinal",
    sort_order: str = "asc",
    offset: int = 0,
    skip: int | None = None,
    limit: int = 50,
) -> tuple[list[KnowledgeChunk], int]:
    conditions = [KnowledgeChunk.chunk_set_id.is_not(None)]
    exact = {
        KnowledgeChunk.chunk_set_id: chunk_set_id,
        KnowledgeChunk.content_type: content_type,
        KnowledgeChunk.language: language,
        KnowledgeChunk.content_hash: content_hash,
    }
    for column, value in exact.items():
        if value is not None:
            conditions.append(column == value)
    if minimum_character_count is not None:
        conditions.append(
            KnowledgeChunk.character_count >= minimum_character_count
        )
    if maximum_character_count is not None:
        conditions.append(
            KnowledgeChunk.character_count <= maximum_character_count
        )
    if page_number is not None:
        conditions.append(
            exists().where(
                ChunkSourceSpan.knowledge_chunk_id == KnowledgeChunk.id,
                ChunkSourceSpan.page_number == page_number,
            )
        )
    if section_path:
        needle = section_path.strip().casefold()
        conditions.append(
            exists().where(
                ChunkSourceSpan.knowledge_chunk_id == KnowledgeChunk.id,
                func.lower(
                    cast(ChunkSourceSpan.section_path_json, String)
                ).contains(needle),
            )
        )
    if text_query:
        needle = text_query.strip().casefold()
        if needle:
            conditions.append(
                func.lower(KnowledgeChunk.text).contains(needle)
            )
    effective_offset = offset if skip is None else skip
    if effective_offset < 0 or not 1 <= limit <= 200:
        raise ResourceValidationError("Chunk pagination is invalid")
    column = _CHUNK_SORT_COLUMNS.get(sort_by)
    if column is None or sort_order.casefold() not in {"asc", "desc"}:
        raise ResourceValidationError("Chunk sorting is invalid")
    order = asc if sort_order.casefold() == "asc" else desc
    total = db.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(*conditions)
    ) or 0
    query = (
        select(KnowledgeChunk)
        .options(selectinload(KnowledgeChunk.source_spans))
        .where(*conditions)
        .order_by(order(column), order(KnowledgeChunk.id))
        .offset(effective_offset)
        .limit(limit)
    )
    return list(db.scalars(query)), total


def get_chunk(db: Session, chunk_id: int) -> KnowledgeChunk:
    chunk = db.scalar(
        select(KnowledgeChunk)
        .options(selectinload(KnowledgeChunk.source_spans))
        .where(
            KnowledgeChunk.id == chunk_id,
            KnowledgeChunk.chunk_set_id.is_not(None),
        )
    )
    if chunk is None:
        raise ResourceNotFoundError("Chunk", chunk_id)
    return chunk


def get_chunk_neighbors(
    db: Session,
    chunk_id: int,
) -> tuple[KnowledgeChunk | None, KnowledgeChunk, KnowledgeChunk | None]:
    chunk = get_chunk(db, chunk_id)
    previous = (
        get_chunk(db, chunk.previous_chunk_id)
        if chunk.previous_chunk_id is not None
        else None
    )
    following = (
        get_chunk(db, chunk.next_chunk_id)
        if chunk.next_chunk_id is not None
        else None
    )
    return previous, chunk, following


def add_chunking_artifact(
    db: Session,
    chunk_set_id: int,
    artifact_type: ChunkingArtifactType | str,
    name: str,
    *,
    content_json: dict[str, Any] | list[Any] | None = None,
    content_text: str | None = None,
    commit: bool = True,
) -> ChunkingArtifact:
    chunk_set = db.get(ChunkSet, chunk_set_id)
    if chunk_set is None:
        raise ResourceNotFoundError("Chunk set", chunk_set_id)
    if chunk_set.status in {
        ChunkSetStatus.SUCCEEDED.value,
        ChunkSetStatus.INVALIDATED.value,
    }:
        raise ResourceConflictError(
            "Successful chunk set artifacts are immutable"
        )
    try:
        resolved_type = (
            artifact_type
            if isinstance(artifact_type, ChunkingArtifactType)
            else ChunkingArtifactType(str(artifact_type).casefold())
        )
    except ValueError as exc:
        raise ResourceValidationError(
            "Chunking artifact type is invalid"
        ) from exc
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 255:
        raise ResourceValidationError(
            "Chunking artifact name must contain 1 to 255 characters"
        )
    if content_json is None and content_text is None:
        raise ResourceValidationError(
            "Chunking artifacts require JSON or text content"
        )
    checksum_payload = (
        json.dumps(
            content_json,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if content_json is not None
        else content_text or ""
    )
    artifact = ChunkingArtifact(
        chunk_set_id=chunk_set.id,
        artifact_type=resolved_type.value,
        name=normalized_name,
        content_json=content_json,
        content_text=content_text,
        checksum=sha256(checksum_payload.encode("utf-8")).hexdigest(),
    )
    db.add(artifact)
    if commit:
        _commit(db, "Chunking artifact could not be created")
        db.refresh(artifact)
    else:
        db.flush()
    return artifact


def list_chunking_artifacts(
    db: Session,
    chunk_set_id: int,
) -> list[ChunkingArtifact]:
    get_chunk_set(db, chunk_set_id)
    return list(
        db.scalars(
            select(ChunkingArtifact)
            .where(ChunkingArtifact.chunk_set_id == chunk_set_id)
            .order_by(ChunkingArtifact.id)
        )
    )


def validate_relationship(
    relationship: ChunkRelationship,
    source: KnowledgeChunk,
    target: KnowledgeChunk,
) -> None:
    if source.id == target.id:
        raise ResourceValidationError("Chunk relationships cannot be self-links")
    if (
        source.chunk_set_id != target.chunk_set_id
        or relationship.chunk_set_id != source.chunk_set_id
    ):
        raise ResourceValidationError(
            "Chunk relationships cannot cross chunk sets"
        )


def _safe_text(value: str, maximum: int) -> str:
    normalized = str(value).replace("\x00", "").strip()
    return (normalized or "unknown")[:maximum]


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    started = started_at
    finished = finished_at
    if started.tzinfo is None and finished.tzinfo is not None:
        finished = finished.replace(tzinfo=None)
    elif started.tzinfo is not None and finished.tzinfo is None:
        started = started.replace(tzinfo=None)
    return max(0, int((finished - started).total_seconds() * 1000))


__all__ = [
    "add_chunking_artifact",
    "begin_chunking_execution",
    "calculate_chunk_content_hash",
    "calculate_chunk_set_content_hash",
    "calculate_configuration_hash",
    "complete_chunking_execution",
    "create_or_get_chunk_set",
    "fail_chunking_execution",
    "get_chunk",
    "get_chunk_neighbors",
    "get_chunk_set",
    "get_chunking_history",
    "get_current_chunk_set",
    "invalidate_chunk_set",
    "list_chunk_sets",
    "list_chunking_artifacts",
    "list_chunks",
    "serialize_chunk_configuration",
    "validate_relationship",
]
