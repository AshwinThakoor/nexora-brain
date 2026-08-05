from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re
import unicodedata
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..chunking import (
    AbstractChunkingStrategy,
    ChunkCandidate,
    ChunkConfiguration,
    ChunkingOutput,
    ChunkingStrategyRegistry,
    default_chunking_registry,
)
from ..config import Settings, get_settings
from ..models import (
    CanonicalDocument,
    ChunkContentType,
    ChunkRelationship,
    ChunkRelationshipType,
    ChunkSet,
    ChunkSetStatus,
    ChunkSourceSpan,
    ChunkingArtifactType,
    KnowledgeChunk,
    ParseResult,
    ParseResultStatus,
)
from . import chunking_service, parse_result_service
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
    ServiceError,
)


def default_chunk_configuration(
    settings: Settings | None = None,
) -> ChunkConfiguration:
    configured = settings or get_settings()
    strategy = select_chunking_strategy(
        configured.chunk_strategy,
        registry=default_chunking_registry,
    )
    return ChunkConfiguration(
        strategy_name=strategy.strategy_name(),
        strategy_version=strategy.strategy_version(),
        target_size=configured.chunk_target_size,
        maximum_size=configured.chunk_maximum_size,
        minimum_size=configured.chunk_minimum_size,
        overlap_size=configured.chunk_overlap_size,
    )


def validate_parse_result_for_chunking(
    db: Session,
    parse_result_id: int,
) -> ParseResult:
    result = parse_result_service.get_parse_result(db, parse_result_id)
    if result.status != ParseResultStatus.SUCCEEDED.value:
        raise ResourceValidationError(
            "Only successful immutable parse results can be chunked"
        )
    if not result.canonical_json:
        raise ResourceValidationError(
            "Parse result has no canonical JSON to chunk"
        )
    if not result.content_hash:
        raise ResourceValidationError(
            "Parse result canonical content hash is missing"
        )
    calculated = parse_result_service.calculate_content_hash(
        result.canonical_json
    )
    if calculated != result.content_hash:
        raise ResourceValidationError(
            "Parse result canonical content hash does not match canonical JSON"
        )
    return result


def select_chunking_strategy(
    strategy_name: str,
    strategy_version: str | None = None,
    *,
    registry: ChunkingStrategyRegistry | None = None,
) -> AbstractChunkingStrategy:
    selected_registry = registry or default_chunking_registry
    try:
        return selected_registry.require(strategy_name, strategy_version)
    except KeyError as exc:
        raise ResourceValidationError(
            "Requested chunking strategy is not available"
        ) from exc


def load_canonical_document(parse_result: ParseResult) -> CanonicalDocument:
    if not parse_result.canonical_json:
        raise ResourceValidationError(
            "Parse result has no canonical JSON to chunk"
        )
    document = parse_result_service.deserialize_canonical_document(
        parse_result.canonical_json
    )
    if document.schema_version != parse_result.canonical_schema_version:
        raise ResourceValidationError(
            "Canonical document schema version does not match ParseResult"
        )
    return document


def generate_chunk_candidates(
    document: CanonicalDocument,
    configuration: ChunkConfiguration,
    *,
    strategy: AbstractChunkingStrategy | None = None,
    registry: ChunkingStrategyRegistry | None = None,
) -> ChunkingOutput:
    selected = strategy or select_chunking_strategy(
        configuration.strategy_name,
        configuration.strategy_version,
        registry=registry,
    )
    if not selected.supports_canonical_schema(document.schema_version):
        raise ResourceValidationError(
            "Chunking strategy does not support the canonical schema version"
        )
    try:
        validated = selected.validate_config(configuration)
        return selected.chunk(document, validated)
    except (TypeError, ValueError) as exc:
        raise ResourceValidationError(
            "Chunking configuration or canonical content is invalid"
        ) from exc


def validate_chunk_candidates(
    candidates: list[ChunkCandidate],
    document: CanonicalDocument,
    configuration: ChunkConfiguration,
) -> None:
    if not candidates:
        raise ResourceValidationError(
            "Chunking produced no citation-ready chunks"
        )
    section_list = list(document.iter_sections())
    paragraph_list = list(document.iter_paragraphs())
    inherited_pages = {
        value
        for value in (
            [
                paragraph.page_number
                for paragraph in paragraph_list
            ]
            + [table.page_number for table in document.tables]
            + [section.page_start for section in section_list]
            + [section.page_end for section in section_list]
            + [
                item.provenance.page_number
                for item in [*section_list, *paragraph_list, *document.tables]
                if item.provenance is not None
            ]
        )
        if value is not None
    }
    inherited_paths = {
        tuple(item.provenance.section_path)
        for item in [*section_list, *paragraph_list, *document.tables]
        if item.provenance is not None
    }

    def add_section_paths(items, parent: tuple[str, ...] = ()) -> None:
        for item in items:
            path = (
                (*parent, item.title)
                if item.title
                else parent
            )
            inherited_paths.add(tuple(path))
            add_section_paths(item.subsections, tuple(path))

    add_section_paths(document.sections)
    previous: ChunkCandidate | None = None
    for ordinal, candidate in enumerate(candidates):
        if candidate.ordinal != ordinal:
            raise ResourceValidationError(
                "Chunk candidate ordinals must be contiguous"
            )
        if not candidate.text:
            raise ResourceValidationError("Chunk candidates cannot be empty")
        if candidate.character_count != len(candidate.text):
            raise ResourceValidationError(
                "Chunk character statistics are inconsistent"
            )
        if candidate.character_count > configuration.maximum_size:
            raise ResourceValidationError(
                "Chunk candidate exceeds maximum_size"
            )
        if not candidate.provenance:
            raise ResourceValidationError(
                "Every chunk must inherit at least one source span"
            )
        if len(candidate.provenance) != len(candidate.source_blocks):
            raise ResourceValidationError(
                "Chunk source blocks and provenance spans are inconsistent"
            )
        orders = [span.source_order for span in candidate.provenance]
        if orders != sorted(orders):
            raise ResourceValidationError(
                "Chunk source span order is not monotonic"
            )
        previous_text_end = -1
        for block, span in zip(
            candidate.source_blocks,
            candidate.provenance,
            strict=True,
        ):
            if (
                span.text_start_in_chunk < previous_text_end
                or span.text_end_in_chunk > len(candidate.text)
                or span.text_end_in_chunk <= span.text_start_in_chunk
            ):
                raise ResourceValidationError(
                    "Chunk source span offsets are invalid"
                )
            inherited_text = candidate.text[
                span.text_start_in_chunk:span.text_end_in_chunk
            ]
            if inherited_text != block.text:
                raise ResourceValidationError(
                    "Chunk source span does not match exact chunk text"
                )
            previous_text_end = span.text_end_in_chunk
            _validate_source_reference(
                span,
                document,
                section_list,
                paragraph_list,
            )
            if (
                span.page_number is not None
                and span.page_number not in inherited_pages
            ):
                raise ResourceValidationError(
                    "Chunk page number was not inherited"
                )
            if (
                span.section_path
                and tuple(span.section_path) not in inherited_paths
            ):
                raise ResourceValidationError(
                    "Chunk section path was not inherited"
                )
            if (
                span.character_end is not None
                and span.character_end > len(document.content)
            ):
                raise ResourceValidationError(
                    "Chunk source character offsets exceed canonical content"
                )
        overlap = candidate.overlap_metadata or {}
        overlap_count = int(overlap.get("character_count", 0))
        if overlap_count:
            if previous is None or overlap_count > configuration.overlap_size:
                raise ResourceValidationError(
                    "Chunk overlap metadata is invalid"
                )
            if candidate.text[:overlap_count] != previous.text[-overlap_count:]:
                raise ResourceValidationError(
                    "Chunk overlap does not match duplicated source text"
                )
            if not any(span.is_overlap for span in candidate.provenance):
                raise ResourceValidationError(
                    "Duplicated overlap spans must be marked"
                )
        previous = candidate


def _validate_source_reference(
    span,
    document: CanonicalDocument,
    sections: list,
    paragraphs: list,
) -> None:
    if span.canonical_block_type == "document_title":
        if not document.metadata.title:
            raise ResourceValidationError(
                "Chunk references a missing document title"
            )
    elif span.canonical_block_type == "section":
        if (
            span.canonical_block_index is None
            or span.canonical_block_index >= len(sections)
        ):
            raise ResourceValidationError(
                "Chunk references a missing canonical section"
            )
    elif span.canonical_block_type == "paragraph":
        indexes = {
            paragraph.provenance.paragraph_index
            for paragraph in paragraphs
            if paragraph.provenance is not None
            and paragraph.provenance.paragraph_index is not None
        }
        if span.paragraph_index is None or (
            span.paragraph_index not in indexes
            and span.paragraph_index >= len(paragraphs)
        ):
            raise ResourceValidationError(
                "Chunk references a missing canonical paragraph"
            )
    elif span.canonical_block_type == "table":
        if (
            span.table_index is None
            or span.table_index >= len(document.tables)
        ):
            raise ResourceValidationError(
                "Chunk references a missing canonical table"
            )
        table = document.tables[span.table_index]
        if (
            span.table_row_end is not None
            and table.rows
            and span.table_row_end >= len(table.rows)
        ):
            raise ResourceValidationError(
                "Chunk table row range exceeds the canonical table"
            )
    else:
        raise ResourceValidationError(
            "Chunk references an unsupported canonical block type"
        )


def persist_chunk_set(
    db: Session,
    chunk_set: ChunkSet,
    output: ChunkingOutput,
    document: CanonicalDocument,
    configuration: ChunkConfiguration,
) -> ChunkSet:
    del document
    if chunk_set.status != ChunkSetStatus.CHUNKING.value:
        raise ResourceConflictError(
            "Chunk set is not in the chunking lifecycle state"
        )
    existing = db.scalar(
        select(KnowledgeChunk.id).where(
            KnowledgeChunk.chunk_set_id == chunk_set.id
        )
    )
    if existing is not None:
        raise ResourceConflictError(
            "Chunk set already contains immutable chunk output"
        )
    persisted: list[KnowledgeChunk] = []
    for candidate in output.chunks:
        content_hash = chunking_service.calculate_chunk_content_hash(candidate)
        stable_key = _stable_key(chunk_set, candidate, content_hash)
        chunk = KnowledgeChunk(
            document_id=None,
            chunk_index=candidate.ordinal,
            category="general",
            content=candidate.text,
            word_count=candidate.estimated_word_count,
            chunk_set_id=chunk_set.id,
            ordinal=candidate.ordinal,
            stable_key=stable_key,
            content_type=candidate.content_type.value,
            text=candidate.text,
            normalized_text=_normalize_text(candidate.text),
            heading_context_json=list(candidate.heading_context),
            language=configuration.language,
            character_count=candidate.character_count,
            content_hash=content_hash,
        )
        db.add(chunk)
        db.flush()
        for span in candidate.provenance:
            db.add(
                ChunkSourceSpan(
                    knowledge_chunk_id=chunk.id,
                    source_order=span.source_order,
                    canonical_block_type=span.canonical_block_type,
                    canonical_block_index=span.canonical_block_index,
                    source_index=span.source_index,
                    page_number=span.page_number,
                    section_path_json=list(span.section_path) or None,
                    paragraph_index=span.paragraph_index,
                    table_index=span.table_index,
                    table_row_start=span.table_row_start,
                    table_row_end=span.table_row_end,
                    character_start=span.character_start,
                    character_end=span.character_end,
                    source_locator=span.source_locator,
                    text_start_in_chunk=span.text_start_in_chunk,
                    text_end_in_chunk=span.text_end_in_chunk,
                    is_overlap=span.is_overlap,
                )
            )
        persisted.append(chunk)
    db.flush()
    for index, chunk in enumerate(persisted):
        chunk.previous_chunk_id = (
            persisted[index - 1].id if index > 0 else None
        )
        chunk.next_chunk_id = (
            persisted[index + 1].id
            if index + 1 < len(persisted)
            else None
        )
    relationships: set[tuple[int, int, str]] = set()
    for candidate in output.chunks:
        current = persisted[candidate.ordinal]
        for hint in candidate.relationship_hints:
            try:
                relationship_type = ChunkRelationshipType(
                    str(hint["type"]).casefold()
                )
                other = persisted[int(hint["target_ordinal"])]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ResourceValidationError(
                    "Chunk relationship hint is invalid"
                ) from exc
            source, target = (
                (other, current)
                if other.ordinal is not None
                and current.ordinal is not None
                and other.ordinal < current.ordinal
                else (current, other)
            )
            key = (source.id, target.id, relationship_type.value)
            if source.id == target.id or key in relationships:
                continue
            relationships.add(key)
            db.add(
                ChunkRelationship(
                    chunk_set_id=chunk_set.id,
                    source_chunk_id=source.id,
                    target_chunk_id=target.id,
                    relationship_type=relationship_type.value,
                    metadata_json={
                        key: value
                        for key, value in hint.items()
                        if key not in {"type", "target_ordinal"}
                    }
                    or None,
                )
            )
    chunking_service.add_chunking_artifact(
        db,
        chunk_set.id,
        ChunkingArtifactType.CONFIGURATION,
        "chunk-configuration",
        content_json=json.loads(chunk_set.configuration_json),
        commit=False,
    )
    chunking_service.add_chunking_artifact(
        db,
        chunk_set.id,
        ChunkingArtifactType.STATISTICS,
        "chunk-statistics",
        content_json=output.statistics.model_dump(mode="json"),
        commit=False,
    )
    manifest = {
        "strategy_name": output.strategy_name,
        "strategy_version": output.strategy_version,
        "configuration_hash": output.configuration_hash,
        "canonical_content_hash": chunk_set.canonical_content_hash,
        "chunks": [
            {
                "ordinal": chunk.ordinal,
                "stable_key": chunk.stable_key,
                "content_hash": chunk.content_hash,
                "character_count": chunk.character_count,
                "word_count": chunk.word_count,
            }
            for chunk in persisted
        ],
    }
    chunking_service.add_chunking_artifact(
        db,
        chunk_set.id,
        ChunkingArtifactType.MANIFEST,
        "chunk-manifest",
        content_json=manifest,
        commit=False,
    )
    chunking_service.add_chunking_artifact(
        db,
        chunk_set.id,
        ChunkingArtifactType.VALIDATION_REPORT,
        "provenance-validation",
        content_json={
            "valid": True,
            "chunk_count": len(persisted),
            "all_chunks_have_source_spans": True,
            "neighbor_links_validated": True,
        },
        commit=False,
    )
    for index, warning in enumerate(output.warnings):
        chunking_service.add_chunking_artifact(
            db,
            chunk_set.id,
            ChunkingArtifactType.WARNING,
            f"chunk-warning-{index + 1}",
            content_text=warning,
            commit=False,
        )
    db.flush()
    return chunk_set


def chunk_parse_result(
    db: Session,
    parse_result_id: int,
    configuration: ChunkConfiguration | Mapping[str, Any] | None = None,
    *,
    registry: ChunkingStrategyRegistry | None = None,
    settings: Settings | None = None,
    node_name: str | None = None,
) -> ChunkSet:
    config = _resolve_configuration(configuration, settings=settings)
    result = validate_parse_result_for_chunking(db, parse_result_id)
    document = load_canonical_document(result)
    strategy = select_chunking_strategy(
        config.strategy_name,
        config.strategy_version,
        registry=registry,
    )
    if not strategy.supports_canonical_schema(document.schema_version):
        raise ResourceValidationError(
            "Chunking strategy does not support the canonical schema version"
        )
    chunk_set = chunking_service.create_or_get_chunk_set(
        db,
        result.id,
        config,
        canonical_content_hash=result.content_hash,
    )
    if chunk_set.status == ChunkSetStatus.SUCCEEDED.value:
        return chunk_set
    execution = None
    try:
        execution = chunking_service.begin_chunking_execution(
            db,
            chunk_set.id,
            node_name=node_name,
        )
        output = generate_chunk_candidates(
            document,
            config,
            strategy=strategy,
            registry=registry,
        )
        validate_chunk_candidates(output.chunks, document, config)
        persist_chunk_set(db, chunk_set, output, document, config)
        content_hash = chunking_service.calculate_chunk_set_content_hash(
            output.chunks
        )
        return chunking_service.complete_chunking_execution(
            db,
            execution.id,
            content_hash=content_hash,
        )
    except Exception as exc:
        db.rollback()
        if execution is not None:
            try:
                chunking_service.fail_chunking_execution(
                    db,
                    execution.id,
                    error_code=type(exc).__name__,
                    error_message=_public_failure_message(exc),
                )
            except (ResourceConflictError, ResourceNotFoundError):
                db.rollback()
        if isinstance(exc, ServiceError):
            raise
        if isinstance(exc, (ValidationError, ValueError, TypeError)):
            raise ResourceValidationError(
                "Chunking failed validation safely"
            ) from exc
        raise ResourceValidationError(
            "Parse result chunking failed safely"
        ) from exc


def rechunk_parse_result(
    db: Session,
    parse_result_id: int,
    configuration: ChunkConfiguration | Mapping[str, Any] | None = None,
    **kwargs,
) -> ChunkSet:
    """Create the identity selected by a new strategy/configuration.

    An identical successful identity is intentionally returned unchanged.
    """

    return chunk_parse_result(
        db,
        parse_result_id,
        configuration,
        **kwargs,
    )


def get_chunking_readiness(
    db: Session,
    parse_result_id: int,
    configuration: ChunkConfiguration | Mapping[str, Any] | None = None,
    *,
    registry: ChunkingStrategyRegistry | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    result = None
    document = None
    strategy = None
    config = None
    try:
        config = _resolve_configuration(configuration, settings=settings)
    except (ValidationError, ValueError, ResourceValidationError) as exc:
        reasons.append(_public_failure_message(exc))
    try:
        result = validate_parse_result_for_chunking(db, parse_result_id)
        document = load_canonical_document(result)
    except ServiceError as exc:
        reasons.append(exc.detail)
    if config is not None:
        try:
            strategy = select_chunking_strategy(
                config.strategy_name,
                config.strategy_version,
                registry=registry,
            )
            strategy.validate_config(config)
            if document is not None and not strategy.supports_canonical_schema(
                document.schema_version
            ):
                reasons.append(
                    "Chunking strategy does not support the canonical schema"
                )
        except (ResourceValidationError, ValueError) as exc:
            reasons.append(_public_failure_message(exc))
    current = (
        chunking_service.get_current_chunk_set(db, parse_result_id)
        if result is not None
        else None
    )
    return {
        "parse_result_id": parse_result_id,
        "ready": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "parse_result_status": result.status if result else None,
        "canonical_schema_version": (
            result.canonical_schema_version if result else None
        ),
        "canonical_hash_valid": result is not None,
        "strategy_name": (
            strategy.strategy_name() if strategy is not None else None
        ),
        "strategy_version": (
            strategy.strategy_version() if strategy is not None else None
        ),
        "configuration_hash": (
            config.configuration_hash() if config is not None else None
        ),
        "current_chunk_set_id": current.id if current else None,
    }


def _resolve_configuration(
    configuration: ChunkConfiguration | Mapping[str, Any] | None,
    *,
    settings: Settings | None,
) -> ChunkConfiguration:
    try:
        if configuration is None:
            return default_chunk_configuration(settings)
        if isinstance(configuration, ChunkConfiguration):
            return ChunkConfiguration.model_validate(
                configuration.model_dump()
            )
        return ChunkConfiguration.model_validate(dict(configuration))
    except (ValidationError, TypeError, ValueError) as exc:
        raise ResourceValidationError(
            "Chunk configuration is invalid"
        ) from exc


def _stable_key(
    chunk_set: ChunkSet,
    candidate: ChunkCandidate,
    content_hash: str,
) -> str:
    provenance = [
        {
            "canonical_block_type": span.canonical_block_type,
            "canonical_block_index": span.canonical_block_index,
            "source_index": span.source_index,
            "page_number": span.page_number,
            "section_path": span.section_path,
            "paragraph_index": span.paragraph_index,
            "table_index": span.table_index,
            "table_row_start": span.table_row_start,
            "table_row_end": span.table_row_end,
            "character_start": span.character_start,
            "character_end": span.character_end,
            "text_start_in_chunk": span.text_start_in_chunk,
            "text_end_in_chunk": span.text_end_in_chunk,
            "is_overlap": span.is_overlap,
        }
        for span in candidate.provenance
    ]
    identity = {
        "parse_result_id": chunk_set.parse_result_id,
        "canonical_content_hash": chunk_set.canonical_content_hash,
        "strategy_name": chunk_set.strategy_name,
        "strategy_version": chunk_set.strategy_version,
        "configuration_hash": chunk_set.configuration_hash,
        "ordinal": candidate.ordinal,
        "provenance": provenance,
        "content_hash": content_hash,
    }
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKC",
        value.replace("\r\n", "\n").replace("\r", "\n"),
    )
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _public_failure_message(exc: Exception) -> str:
    if isinstance(exc, ServiceError):
        return exc.detail[:2000]
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        return "Chunking input failed deterministic validation"
    return "Parse result chunking failed safely"


__all__ = [
    "chunk_parse_result",
    "default_chunk_configuration",
    "generate_chunk_candidates",
    "get_chunking_readiness",
    "load_canonical_document",
    "persist_chunk_set",
    "rechunk_parse_result",
    "select_chunking_strategy",
    "validate_chunk_candidates",
    "validate_parse_result_for_chunking",
]
