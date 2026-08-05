from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import (
    CanonicalDocument,
    ParseArtifact,
    ParseArtifactType,
    ParseExecution,
    ParseExecutionStatus,
    ParseResult,
    ParseResultStatus,
    DocumentVersion,
    IngestionJob,
    StoredFile,
)
from ..models.common import utc_now
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


_SORT_COLUMNS = {
    "id": ParseResult.id,
    "stored_file_id": ParseResult.stored_file_id,
    "document_version_id": ParseResult.document_version_id,
    "ingestion_job_id": ParseResult.ingestion_job_id,
    "parser_name": ParseResult.parser_name,
    "parser_version": ParseResult.parser_version,
    "status": ParseResult.status,
    "input_sha256": ParseResult.input_sha256,
    "content_hash": ParseResult.content_hash,
    "created_at": ParseResult.created_at,
    "updated_at": ParseResult.updated_at,
    "completed_at": ParseResult.completed_at,
}


def _result_query():
    return (
        select(ParseResult)
        .options(
            selectinload(ParseResult.executions),
            selectinload(ParseResult.artifacts),
        )
        .execution_options(populate_existing=True)
    )


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def _normalize_sha256(value: str) -> str:
    normalized = value.strip().casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ResourceValidationError(
            "Parser input SHA-256 must be 64 hexadecimal characters"
        )
    return normalized


def _normalize_parser_identifier(
    value: str,
    *,
    label: str,
    maximum: int,
) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ResourceValidationError(
            f"{label} must contain between 1 and {maximum} characters"
        )
    return normalized


def serialize_canonical_document(document: CanonicalDocument) -> str:
    try:
        validated = CanonicalDocument.model_validate(document.model_dump())
        validated.assert_valid()
        return json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise ResourceValidationError(
            "Canonical parser output is invalid"
        ) from exc


def deserialize_canonical_document(value: str) -> CanonicalDocument:
    try:
        payload = json.loads(value)
        document = CanonicalDocument.model_validate(payload)
        document.assert_valid()
        return document
    except (
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        TypeError,
    ) as exc:
        raise ResourceValidationError(
            "Persisted canonical parser output is invalid"
        ) from exc


def calculate_content_hash(
    value: CanonicalDocument | str | Mapping[str, Any],
) -> str:
    if isinstance(value, CanonicalDocument):
        serialized = serialize_canonical_document(value)
    elif isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ResourceValidationError(
                "Canonical JSON is invalid"
            ) from exc
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        serialized = json.dumps(
            dict(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return sha256(serialized.encode("utf-8")).hexdigest()


def create_or_get_parse_result(
    db: Session,
    stored_file_id: int,
    parser_name: str,
    parser_version: str,
    *,
    document_version_id: int | None = None,
    ingestion_job_id: int | None = None,
    input_sha256: str | None = None,
    canonical_schema_version: str = "1.0",
) -> ParseResult:
    stored_file = db.get(StoredFile, stored_file_id)
    if stored_file is None:
        raise ResourceNotFoundError("Stored file", stored_file_id)
    normalized_name = _normalize_parser_identifier(
        parser_name,
        label="Parser name",
        maximum=100,
    )
    normalized_version = _normalize_parser_identifier(
        parser_version,
        label="Parser version",
        maximum=64,
    )
    schema_version = _normalize_parser_identifier(
        canonical_schema_version,
        label="Canonical schema version",
        maximum=32,
    )
    normalized_hash = _normalize_sha256(
        input_sha256 or stored_file.sha256
    )
    if normalized_hash != stored_file.sha256.casefold():
        raise ResourceValidationError(
            "Parser input SHA-256 does not match the StoredFile"
        )
    resolved_version_id = (
        stored_file.document_version_id
        if document_version_id is None
        else int(document_version_id)
    )
    if resolved_version_id != stored_file.document_version_id:
        raise ResourceValidationError(
            "Parse result document version does not match the StoredFile"
        )
    version = db.get(DocumentVersion, resolved_version_id)
    if version is None:
        raise ResourceNotFoundError(
            "Document version",
            resolved_version_id,
        )
    if ingestion_job_id is not None:
        job = db.get(IngestionJob, ingestion_job_id)
        if job is None:
            raise ResourceNotFoundError(
                "Ingestion job",
                ingestion_job_id,
            )
        if job.document_id != version.document_id:
            raise ResourceValidationError(
                "Parse result ingestion job does not belong to "
                "the StoredFile document"
            )
    existing = db.scalar(
        _result_query().where(
            ParseResult.stored_file_id == stored_file.id,
            ParseResult.input_sha256 == normalized_hash,
            ParseResult.parser_name == normalized_name,
            ParseResult.parser_version == normalized_version,
        )
    )
    if existing is not None:
        return existing
    result = ParseResult(
        stored_file_id=stored_file.id,
        document_version_id=resolved_version_id,
        ingestion_job_id=ingestion_job_id,
        parser_name=normalized_name,
        parser_version=normalized_version,
        input_sha256=normalized_hash,
        canonical_schema_version=schema_version,
        status=ParseResultStatus.PENDING.value,
        started_at=utc_now(),
    )
    db.add(result)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(
            _result_query().where(
                ParseResult.stored_file_id == stored_file.id,
                ParseResult.input_sha256 == normalized_hash,
                ParseResult.parser_name == normalized_name,
                ParseResult.parser_version == normalized_version,
            )
        )
        if concurrent is not None:
            return concurrent
        raise ResourceConflictError(
            "Parse result identity already exists"
        )
    return get_parse_result(db, result.id)


def begin_parse_execution(
    db: Session,
    parse_result_id: int,
    *,
    node_name: str | None = None,
    allow_succeeded: bool = False,
) -> ParseExecution:
    result = db.scalar(
        select(ParseResult)
        .where(ParseResult.id == parse_result_id)
        .with_for_update()
    )
    if result is None:
        raise ResourceNotFoundError("Parse result", parse_result_id)
    if result.status == ParseResultStatus.INVALIDATED.value:
        raise ResourceConflictError(
            "Immutable parse result cannot start another execution"
        )
    verifying_immutable_result = (
        result.status == ParseResultStatus.SUCCEEDED.value
        and allow_succeeded
    )
    if (
        result.status == ParseResultStatus.SUCCEEDED.value
        and not verifying_immutable_result
    ):
        raise ResourceConflictError(
            "Immutable parse result cannot start another execution"
        )
    running = db.scalar(
        select(ParseExecution).where(
            ParseExecution.parse_result_id == result.id,
            ParseExecution.status == ParseExecutionStatus.RUNNING.value,
            ParseExecution.finished_at.is_(None),
        )
    )
    if running is not None:
        raise ResourceConflictError(
            "Parse result already has a running execution"
        )
    last_attempt = db.scalar(
        select(func.max(ParseExecution.attempt_number)).where(
            ParseExecution.parse_result_id == result.id
        )
    ) or 0
    normalized_node = node_name.strip() if node_name else None
    execution = ParseExecution(
        parse_result_id=result.id,
        attempt_number=last_attempt + 1,
        status=ParseExecutionStatus.RUNNING.value,
        started_at=utc_now(),
        parser_name=result.parser_name,
        parser_version=result.parser_version,
        node_name=normalized_node or None,
    )
    db.add(execution)
    if not verifying_immutable_result:
        result.status = ParseResultStatus.PARSING.value
        result.completed_at = None
    _commit(db, "Parse execution could not be started")
    db.refresh(execution)
    return execution


def complete_parse_execution(
    db: Session,
    execution_id: int,
    canonical_document: CanonicalDocument,
    *,
    statistics: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    commit: bool = True,
) -> ParseResult:
    execution = db.scalar(
        select(ParseExecution)
        .where(ParseExecution.id == execution_id)
        .with_for_update()
    )
    if execution is None:
        raise ResourceNotFoundError("Parse execution", execution_id)
    if (
        execution.status != ParseExecutionStatus.RUNNING.value
        or execution.finished_at is not None
    ):
        raise ResourceConflictError("Parse execution is already complete")
    result = db.scalar(
        select(ParseResult)
        .where(ParseResult.id == execution.parse_result_id)
        .with_for_update()
    )
    if result is None:
        raise ResourceNotFoundError(
            "Parse result",
            execution.parse_result_id,
        )
    verifying_immutable_result = (
        result.status == ParseResultStatus.SUCCEEDED.value
    )
    if (
        result.status != ParseResultStatus.PARSING.value
        and not verifying_immutable_result
    ):
        raise ResourceConflictError(
            "Parse result is not in the parsing state"
        )
    if (
        canonical_document.parser_name != result.parser_name
        or canonical_document.parser_version != result.parser_version
    ):
        raise ResourceValidationError(
            "Canonical parser identity does not match the ParseResult"
        )
    serialized = serialize_canonical_document(canonical_document)
    content_hash = calculate_content_hash(serialized)
    if verifying_immutable_result and (
        result.content_hash != content_hash
        or result.canonical_json != serialized
    ):
        raise ResourceConflictError(
            "Reparse output differs from the immutable successful result"
        )
    finished_at = utc_now()
    execution.finished_at = finished_at
    execution.duration_ms = _duration_ms(
        execution.started_at,
        finished_at,
    )
    execution.status = ParseExecutionStatus.SUCCEEDED.value
    execution.error_code = None
    execution.error_message = None
    if not verifying_immutable_result:
        result.status = ParseResultStatus.SUCCEEDED.value
        result.content_hash = content_hash
        result.canonical_json = serialized
        result.statistics_json = dict(
            statistics
            if statistics is not None
            else canonical_document.statistics.model_dump(mode="json")
        )
        result.metadata_json = dict(
            metadata
            if metadata is not None
            else canonical_document.metadata.model_dump(mode="json")
        )
        result.completed_at = finished_at
    if commit:
        _commit(db, "Parse result could not be completed")
        return get_parse_result(db, result.id)
    db.flush()
    return result


def fail_parse_execution(
    db: Session,
    execution_id: int,
    *,
    error_code: str,
    error_message: str,
) -> ParseResult:
    execution = db.scalar(
        select(ParseExecution)
        .where(ParseExecution.id == execution_id)
        .with_for_update()
    )
    if execution is None:
        raise ResourceNotFoundError("Parse execution", execution_id)
    if (
        execution.status != ParseExecutionStatus.RUNNING.value
        or execution.finished_at is not None
    ):
        raise ResourceConflictError("Parse execution is already complete")
    result = db.scalar(
        select(ParseResult)
        .where(ParseResult.id == execution.parse_result_id)
        .with_for_update()
    )
    if result is None:
        raise ResourceNotFoundError(
            "Parse result",
            execution.parse_result_id,
        )
    normalized_code = re.sub(
        r"[^A-Z0-9_]+",
        "_",
        error_code.strip().upper(),
    ).strip("_")[:100]
    if not normalized_code:
        normalized_code = "PARSER_ERROR"
    safe_message = _safe_error_message(error_message)
    finished_at = utc_now()
    execution.status = ParseExecutionStatus.FAILED.value
    execution.finished_at = finished_at
    execution.duration_ms = _duration_ms(
        execution.started_at,
        finished_at,
    )
    execution.error_code = normalized_code
    execution.error_message = safe_message
    if result.status != ParseResultStatus.SUCCEEDED.value:
        result.status = ParseResultStatus.FAILED.value
        result.completed_at = finished_at
    _commit(db, "Parse failure could not be recorded")
    return get_parse_result(db, result.id)


def invalidate_parse_result(
    db: Session,
    result_id: int,
) -> ParseResult:
    result = db.scalar(
        select(ParseResult)
        .where(ParseResult.id == result_id)
        .with_for_update()
    )
    if result is None:
        raise ResourceNotFoundError("Parse result", result_id)
    if result.status == ParseResultStatus.INVALIDATED.value:
        db.rollback()
        return get_parse_result(db, result.id)
    if result.status != ParseResultStatus.SUCCEEDED.value:
        raise ResourceValidationError(
            "Only a successful parse result can be invalidated"
        )
    result.status = ParseResultStatus.INVALIDATED.value
    _commit(db, "Parse result could not be invalidated")
    return get_parse_result(db, result.id)


def get_parse_result(db: Session, result_id: int) -> ParseResult:
    result = db.scalar(
        _result_query().where(ParseResult.id == result_id)
    )
    if result is None:
        raise ResourceNotFoundError("Parse result", result_id)
    return result


def get_current_parse_result(
    db: Session,
    stored_file_id: int,
    *,
    parser_name: str | None = None,
    parser_version: str | None = None,
) -> ParseResult | None:
    filters = [
        ParseResult.stored_file_id == stored_file_id,
        ParseResult.status == ParseResultStatus.SUCCEEDED.value,
    ]
    if parser_name is not None:
        filters.append(ParseResult.parser_name == parser_name.strip())
    if parser_version is not None:
        filters.append(ParseResult.parser_version == parser_version.strip())
    return db.scalar(
        _result_query()
        .where(*filters)
        .order_by(
            desc(ParseResult.completed_at),
            desc(ParseResult.id),
        )
        .limit(1)
    )


def list_parse_results(
    db: Session,
    *,
    stored_file_id: int | None = None,
    document_version_id: int | None = None,
    ingestion_job_id: int | None = None,
    parser_name: str | None = None,
    parser_version: str | None = None,
    status: ParseResultStatus | str | None = None,
    input_sha256: str | None = None,
    content_hash: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    offset: int = 0,
    skip: int | None = None,
    limit: int = 50,
) -> tuple[list[ParseResult], int]:
    effective_offset = offset if skip is None else skip
    if effective_offset < 0:
        raise ResourceValidationError("Parse result offset cannot be negative")
    if not 1 <= limit <= 200:
        raise ResourceValidationError(
            "Parse result limit must be between 1 and 200"
        )
    filters = []
    if stored_file_id is not None:
        filters.append(ParseResult.stored_file_id == stored_file_id)
    if document_version_id is not None:
        filters.append(
            ParseResult.document_version_id == document_version_id
        )
    if ingestion_job_id is not None:
        filters.append(ParseResult.ingestion_job_id == ingestion_job_id)
    if parser_name is not None:
        filters.append(ParseResult.parser_name == parser_name.strip())
    if parser_version is not None:
        filters.append(ParseResult.parser_version == parser_version.strip())
    if status is not None:
        try:
            normalized_status = ParseResultStatus(
                str(status).strip().casefold()
            ).value
        except ValueError as exc:
            raise ResourceValidationError(
                "Unsupported parse result status"
            ) from exc
        filters.append(ParseResult.status == normalized_status)
    if input_sha256 is not None:
        filters.append(
            ParseResult.input_sha256 == _normalize_sha256(input_sha256)
        )
    if content_hash is not None:
        filters.append(
            ParseResult.content_hash == _normalize_sha256(content_hash)
        )
    if created_from is not None:
        filters.append(ParseResult.created_at >= created_from)
    if created_to is not None:
        filters.append(ParseResult.created_at <= created_to)
    column = _SORT_COLUMNS.get(sort_by)
    if column is None:
        raise ResourceValidationError("Unsupported parse result sort field")
    order = sort_order.strip().casefold()
    if order not in {"asc", "desc"}:
        raise ResourceValidationError(
            "Parse result sort order must be 'asc' or 'desc'"
        )
    direction = asc if order == "asc" else desc
    total = db.scalar(
        select(func.count()).select_from(ParseResult).where(*filters)
    ) or 0
    statement = (
        _result_query()
        .where(*filters)
        .order_by(direction(column), direction(ParseResult.id))
        .offset(effective_offset)
        .limit(limit)
    )
    return list(db.scalars(statement)), total


def get_parse_history(
    db: Session,
    result_id: int,
) -> list[ParseExecution]:
    get_parse_result(db, result_id)
    return list(
        db.scalars(
            select(ParseExecution)
            .where(ParseExecution.parse_result_id == result_id)
            .order_by(
                ParseExecution.attempt_number,
                ParseExecution.id,
            )
        )
    )


def add_parse_artifact(
    db: Session,
    result_id: int,
    artifact_type: ParseArtifactType | str,
    name: str,
    *,
    mime_type: str | None = None,
    content_json: Mapping[str, Any] | list[Any] | None = None,
    content_text: str | None = None,
    commit: bool = True,
) -> ParseArtifact:
    if db.get(ParseResult, result_id) is None:
        raise ResourceNotFoundError("Parse result", result_id)
    try:
        normalized_type = ParseArtifactType(
            str(artifact_type).strip().casefold()
        ).value
    except ValueError as exc:
        raise ResourceValidationError(
            "Unsupported parse artifact type"
        ) from exc
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 255:
        raise ResourceValidationError(
            "Parse artifact name must contain between 1 and 255 characters"
        )
    if content_json is None and not (content_text or "").strip():
        raise ResourceValidationError(
            "Parse artifact must contain JSON or text content"
        )
    payload_json: dict[str, Any] | list[Any] | None
    if isinstance(content_json, Mapping):
        payload_json = dict(content_json)
    else:
        payload_json = content_json
    normalized_text = content_text if content_text is not None else None
    if payload_json is not None:
        checksum_source = json.dumps(
            payload_json,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        checksum_source = normalized_text or ""
    artifact = ParseArtifact(
        parse_result_id=result_id,
        artifact_type=normalized_type,
        name=normalized_name,
        mime_type=mime_type.strip() if mime_type else None,
        content_json=payload_json,
        content_text=normalized_text,
        checksum=sha256(checksum_source.encode("utf-8")).hexdigest(),
    )
    db.add(artifact)
    if commit:
        _commit(db, "Parse artifact could not be created")
        db.refresh(artifact)
    else:
        db.flush()
    return artifact


def _safe_error_message(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return "Parsing failed"
    normalized = re.sub(
        r"(?:[A-Za-z]:\\|/)(?:[^ \t:]+[/\\])+[^ \t:]+",
        "[internal path]",
        normalized,
    )
    return normalized[:2000]


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    start = started_at
    finish = finished_at
    if start.tzinfo is None and finish.tzinfo is not None:
        finish = finish.replace(tzinfo=None)
    elif start.tzinfo is not None and finish.tzinfo is None:
        finish = finish.replace(tzinfo=timezone.utc)
    return max(0, int((finish - start).total_seconds() * 1000))


__all__ = [
    "add_parse_artifact",
    "begin_parse_execution",
    "calculate_content_hash",
    "complete_parse_execution",
    "create_or_get_parse_result",
    "deserialize_canonical_document",
    "fail_parse_execution",
    "get_current_parse_result",
    "get_parse_history",
    "get_parse_result",
    "invalidate_parse_result",
    "list_parse_results",
    "serialize_canonical_document",
]
