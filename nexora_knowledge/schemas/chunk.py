from __future__ import annotations

from datetime import datetime
from typing import Any, Annotated

from pydantic import BaseModel, Field, StringConstraints

from ..chunking.models import ChunkConfiguration
from .common import ORMResponse


class ChunkRequest(BaseModel):
    configuration: ChunkConfiguration | None = None
    node_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ] | None = None


class RechunkRequest(ChunkRequest):
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ] | None = None


class ChunkingReadinessRead(BaseModel):
    parse_result_id: int
    ready: bool
    reasons: list[str] = Field(default_factory=list)
    parse_result_status: str | None = None
    canonical_schema_version: str | None = None
    canonical_hash_valid: bool = False
    strategy_name: str | None = None
    strategy_version: str | None = None
    configuration_hash: str | None = None
    current_chunk_set_id: int | None = None


class ChunkSourceSpanRead(ORMResponse):
    id: int
    knowledge_chunk_id: int
    source_order: int
    canonical_block_type: str
    canonical_block_index: int | None
    source_index: int | None
    page_number: int | None
    section_path_json: list[Any] | None
    paragraph_index: int | None
    table_index: int | None
    table_row_start: int | None
    table_row_end: int | None
    character_start: int | None
    character_end: int | None
    source_locator: str | None
    text_start_in_chunk: int
    text_end_in_chunk: int
    is_overlap: bool
    created_at: datetime


class ChunkRelationshipRead(ORMResponse):
    id: int
    chunk_set_id: int
    source_chunk_id: int
    target_chunk_id: int
    relationship_type: str
    metadata_json: dict[str, Any] | list[Any] | None
    created_at: datetime


class ChunkingExecutionRead(ORMResponse):
    id: int
    chunk_set_id: int
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    strategy_name: str
    strategy_version: str
    node_name: str | None
    created_at: datetime


class ChunkingArtifactRead(ORMResponse):
    id: int
    chunk_set_id: int
    artifact_type: str
    name: str
    content_json: dict[str, Any] | list[Any] | None
    content_text: str | None
    checksum: str | None
    created_at: datetime


class KnowledgeChunkSummary(ORMResponse):
    id: int
    uuid: str | None
    chunk_set_id: int
    ordinal: int
    stable_key: str
    content_type: str
    heading_context_json: list[Any] | dict[str, Any] | None
    language: str | None
    character_count: int
    word_count: int
    content_hash: str
    previous_chunk_id: int | None
    next_chunk_id: int | None
    created_at: datetime


class KnowledgeChunkRead(KnowledgeChunkSummary):
    text: str
    normalized_text: str | None
    source_spans: list[ChunkSourceSpanRead] = Field(default_factory=list)


class ChunkSetSummary(ORMResponse):
    id: int
    uuid: str
    parse_result_id: int
    document_version_id: int
    stored_file_id: int
    strategy_name: str
    strategy_version: str
    configuration_hash: str
    canonical_content_hash: str
    status: str
    chunk_count: int
    total_character_count: int
    total_word_count: int
    content_hash: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChunkSetRead(ChunkSetSummary):
    configuration_json: str
    chunks: list[KnowledgeChunkSummary] = Field(default_factory=list)
    executions: list[ChunkingExecutionRead] = Field(default_factory=list)
    relationships: list[ChunkRelationshipRead] = Field(default_factory=list)
    artifacts: list[ChunkingArtifactRead] = Field(default_factory=list)


class ChunkingHistoryRead(BaseModel):
    chunk_set: ChunkSetSummary
    executions: list[ChunkingExecutionRead]


class ChunkNeighborsRead(BaseModel):
    previous: KnowledgeChunkSummary | None
    current: KnowledgeChunkRead
    next: KnowledgeChunkSummary | None


class ChunkSetSearch(BaseModel):
    items: list[ChunkSetSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class KnowledgeChunkSearch(BaseModel):
    items: list[KnowledgeChunkSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


__all__ = [
    "ChunkConfiguration",
    "ChunkNeighborsRead",
    "ChunkRelationshipRead",
    "ChunkRequest",
    "ChunkSetRead",
    "ChunkSetSearch",
    "ChunkSetSummary",
    "ChunkSourceSpanRead",
    "ChunkingArtifactRead",
    "ChunkingExecutionRead",
    "ChunkingHistoryRead",
    "ChunkingReadinessRead",
    "KnowledgeChunkRead",
    "KnowledgeChunkSearch",
    "KnowledgeChunkSummary",
    "RechunkRequest",
]
