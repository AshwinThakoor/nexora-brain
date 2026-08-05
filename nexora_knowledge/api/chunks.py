from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from ..models import AcademyRole, ChunkSet, KnowledgeChunk
from ..schemas.chunk import (
    ChunkNeighborsRead,
    ChunkRequest,
    ChunkSetRead,
    ChunkSetSearch,
    ChunkSetSummary,
    ChunkingArtifactRead,
    ChunkingHistoryRead,
    ChunkingReadinessRead,
    KnowledgeChunkRead,
    KnowledgeChunkSearch,
    KnowledgeChunkSummary,
    RechunkRequest,
)
from ..services import chunking_pipeline_service, chunking_service
from ..services.authorization import (
    Principal,
    require_chunk_admin,
    require_chunk_provenance_reader,
    require_chunk_reader,
)
from .dependencies import get_current_principal, get_db


parse_result_router = APIRouter(
    prefix="/api/v1/parse-results",
    tags=["deterministic-chunking"],
)
chunk_set_router = APIRouter(
    prefix="/api/v1/chunk-sets",
    tags=["deterministic-chunking"],
)
chunk_router = APIRouter(
    prefix="/api/v1/chunks",
    tags=["deterministic-chunking"],
)


@parse_result_router.post(
    "/{parse_result_id}/chunk",
    response_model=ChunkSetRead,
)
def chunk_parse_result(
    parse_result_id: int,
    payload: Annotated[ChunkRequest, Body()],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_admin(principal)
    result = chunking_pipeline_service.chunk_parse_result(
        db,
        parse_result_id,
        payload.configuration,
        node_name=payload.node_name,
    )
    return _chunk_set_payload(result, include_internal=True)


@parse_result_router.post(
    "/{parse_result_id}/rechunk",
    response_model=ChunkSetRead,
)
def rechunk_parse_result(
    parse_result_id: int,
    payload: Annotated[RechunkRequest, Body()],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_admin(principal)
    result = chunking_pipeline_service.rechunk_parse_result(
        db,
        parse_result_id,
        payload.configuration,
        node_name=payload.node_name,
    )
    return _chunk_set_payload(result, include_internal=True)


@parse_result_router.get(
    "/{parse_result_id}/chunk-readiness",
    response_model=ChunkingReadinessRead,
)
def chunk_readiness(
    parse_result_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_reader(principal)
    return chunking_pipeline_service.get_chunking_readiness(
        db,
        parse_result_id,
    )


@parse_result_router.get(
    "/{parse_result_id}/chunk-sets",
    response_model=ChunkSetSearch,
)
def list_parse_result_chunk_sets(
    parse_result_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    status: str | None = None,
    strategy_name: str | None = None,
    strategy_version: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    require_chunk_reader(principal)
    items, total = chunking_service.list_chunk_sets(
        db,
        parse_result_id=parse_result_id,
        status=status,
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        skip=skip,
        limit=limit,
    )
    return _set_search(items, total, offset, skip, limit)


@chunk_set_router.get("", response_model=ChunkSetSearch)
def list_chunk_sets(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
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
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    require_chunk_reader(principal)
    items, total = chunking_service.list_chunk_sets(
        db,
        parse_result_id=parse_result_id,
        document_version_id=document_version_id,
        stored_file_id=stored_file_id,
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        status=status,
        configuration_hash=configuration_hash,
        canonical_content_hash=canonical_content_hash,
        content_hash=content_hash,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        skip=skip,
        limit=limit,
    )
    return _set_search(items, total, offset, skip, limit)


@chunk_set_router.get("/{chunk_set_id}", response_model=ChunkSetRead)
def read_chunk_set(
    chunk_set_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_reader(principal)
    result = chunking_service.get_chunk_set(db, chunk_set_id)
    return _chunk_set_payload(
        result,
        include_internal=principal.role in {
            AcademyRole.REVIEWER,
            AcademyRole.ADMIN,
        },
    )


@chunk_set_router.get(
    "/{chunk_set_id}/history",
    response_model=ChunkingHistoryRead,
)
def read_chunking_history(
    chunk_set_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_provenance_reader(principal)
    chunk_set = chunking_service.get_chunk_set(db, chunk_set_id)
    return ChunkingHistoryRead(
        chunk_set=ChunkSetSummary.model_validate(chunk_set),
        executions=chunking_service.get_chunking_history(db, chunk_set_id),
    )


@chunk_set_router.get(
    "/{chunk_set_id}/artifacts",
    response_model=list[ChunkingArtifactRead],
)
def read_chunking_artifacts(
    chunk_set_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_provenance_reader(principal)
    return chunking_service.list_chunking_artifacts(db, chunk_set_id)


@chunk_set_router.get(
    "/{chunk_set_id}/chunks",
    response_model=KnowledgeChunkSearch,
)
def list_chunk_set_chunks(
    chunk_set_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
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
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    require_chunk_reader(principal)
    chunking_service.get_chunk_set(db, chunk_set_id)
    items, total = chunking_service.list_chunks(
        db,
        chunk_set_id=chunk_set_id,
        content_type=content_type,
        language=language,
        content_hash=content_hash,
        minimum_character_count=minimum_character_count,
        maximum_character_count=maximum_character_count,
        page_number=page_number,
        section_path=section_path,
        text_query=text_query,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        skip=skip,
        limit=limit,
    )
    effective_offset = offset if skip is None else skip
    return KnowledgeChunkSearch(
        items=[
            KnowledgeChunkSummary.model_validate(item) for item in items
        ],
        total=total,
        offset=effective_offset,
        skip=effective_offset,
        limit=limit,
    )


@chunk_set_router.post(
    "/{chunk_set_id}/invalidate",
    response_model=ChunkSetRead,
)
def invalidate_chunk_set(
    chunk_set_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_admin(principal)
    result = chunking_service.invalidate_chunk_set(db, chunk_set_id)
    return _chunk_set_payload(result, include_internal=True)


@chunk_router.get("/{chunk_id}", response_model=KnowledgeChunkRead)
def read_chunk(
    chunk_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_reader(principal)
    chunk = chunking_service.get_chunk(db, chunk_id)
    return _chunk_payload(
        chunk,
        include_provenance=principal.role in {
            AcademyRole.REVIEWER,
            AcademyRole.ADMIN,
        },
    )


@chunk_router.get(
    "/{chunk_id}/neighbors",
    response_model=ChunkNeighborsRead,
)
def read_chunk_neighbors(
    chunk_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_chunk_reader(principal)
    previous, current, following = chunking_service.get_chunk_neighbors(
        db,
        chunk_id,
    )
    include_provenance = principal.role in {
        AcademyRole.REVIEWER,
        AcademyRole.ADMIN,
    }
    return ChunkNeighborsRead(
        previous=(
            KnowledgeChunkSummary.model_validate(previous)
            if previous is not None
            else None
        ),
        current=_chunk_payload(
            current,
            include_provenance=include_provenance,
        ),
        next=(
            KnowledgeChunkSummary.model_validate(following)
            if following is not None
            else None
        ),
    )


def _chunk_payload(
    chunk: KnowledgeChunk,
    *,
    include_provenance: bool,
) -> KnowledgeChunkRead:
    summary = KnowledgeChunkSummary.model_validate(chunk)
    return KnowledgeChunkRead(
        **summary.model_dump(),
        text=chunk.text or chunk.content,
        normalized_text=chunk.normalized_text,
        source_spans=chunk.source_spans if include_provenance else [],
    )


def _chunk_set_payload(
    chunk_set: ChunkSet,
    *,
    include_internal: bool,
) -> ChunkSetRead:
    summary = ChunkSetSummary.model_validate(chunk_set)
    return ChunkSetRead(
        **summary.model_dump(),
        configuration_json=chunk_set.configuration_json,
        chunks=[
            KnowledgeChunkSummary.model_validate(chunk)
            for chunk in chunk_set.chunks
        ],
        executions=chunk_set.executions if include_internal else [],
        relationships=chunk_set.relationships if include_internal else [],
        artifacts=chunk_set.artifacts if include_internal else [],
    )


def _set_search(
    items: list[ChunkSet],
    total: int,
    offset: int,
    skip: int | None,
    limit: int,
) -> ChunkSetSearch:
    effective_offset = offset if skip is None else skip
    return ChunkSetSearch(
        items=[ChunkSetSummary.model_validate(item) for item in items],
        total=total,
        offset=effective_offset,
        skip=effective_offset,
        limit=limit,
    )


__all__ = ["chunk_router", "chunk_set_router", "parse_result_router"]
