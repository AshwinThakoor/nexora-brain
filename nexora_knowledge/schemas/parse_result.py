from __future__ import annotations

from datetime import datetime
from typing import Any, Annotated

from pydantic import BaseModel, Field, StringConstraints

from ..models.canonical_document import CanonicalDocument
from .common import ORMResponse, PositiveId


ParserIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class ParseRequest(BaseModel):
    ingestion_job_id: PositiveId | None = None


class ReparseRequest(ParseRequest):
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ] | None = None


class ParseExecutionRead(ORMResponse):
    id: int
    parse_result_id: int
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    parser_name: str
    parser_version: str
    node_name: str | None
    created_at: datetime


class ParseArtifactRead(ORMResponse):
    id: int
    parse_result_id: int
    artifact_type: str
    name: str
    mime_type: str | None
    content_json: dict[str, Any] | list[Any] | None
    content_text: str | None
    checksum: str | None
    created_at: datetime


class ParseResultSummary(ORMResponse):
    id: int
    uuid: str
    stored_file_id: int
    document_version_id: int
    ingestion_job_id: int | None
    parser_name: str
    parser_version: str
    input_sha256: str
    canonical_schema_version: str
    status: str
    content_hash: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ParseResultRead(ParseResultSummary):
    canonical_json: dict[str, Any] | None = None
    canonical_document: CanonicalDocument | None = None
    statistics_json: dict[str, Any] | list[Any] | None
    metadata_json: dict[str, Any] | list[Any] | None
    executions: list[ParseExecutionRead] = Field(default_factory=list)
    artifacts: list[ParseArtifactRead] = Field(default_factory=list)


class ParseHistoryRead(BaseModel):
    result: ParseResultSummary
    executions: list[ParseExecutionRead]


class ParseReadinessRead(BaseModel):
    file_id: int
    ready: bool
    reasons: list[str] = Field(default_factory=list)
    parser_name: str | None = None
    parser_version: str | None = None
    ingestion_job_id: int | None = None
    ingestion_status: str | None = None
    storage_exists: bool = False
    size_within_limit: bool = False
    mime_extension_match: bool = False
    document_version_valid: bool = False
    ingestion_eligible: bool = False


class ParseResultSearch(BaseModel):
    items: list[ParseResultSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


__all__ = [
    "ParseArtifactRead",
    "ParseExecutionRead",
    "ParseHistoryRead",
    "ParseReadinessRead",
    "ParseRequest",
    "ParseResultRead",
    "ParseResultSearch",
    "ParseResultSummary",
    "ReparseRequest",
]
