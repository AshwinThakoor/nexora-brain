from __future__ import annotations

from datetime import timezone
from hashlib import sha256

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import (
    DocumentVersion,
    IngestionJob,
    JobStatus,
    ParseArtifactType,
    ParseResult,
    ParseResultStatus,
    StoredFile,
)
from ..models.common import utc_now
from ..parsers import ParserError, default_registry
from ..parsers.base import AbstractParser
from ..parsers.registry import ParserRegistry
from ..schemas.parse_result import ParseReadinessRead
from ..storage.providers import (
    AbstractStorageProvider,
    get_default_storage_provider,
)
from . import ingestion_service, parse_result_service
from .document_service import validate_ingestion_eligibility
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
    ServiceError,
)
from .parser_service import validate_document
from .storage_service import get_file


_PIPELINE_JOB_STATUSES = frozenset(
    {
        JobStatus.RESERVED.value,
        JobStatus.RUNNING.value,
    }
)


def select_parser_for_stored_file(
    stored_file: StoredFile,
    *,
    registry: ParserRegistry | None = None,
) -> AbstractParser:
    selected_registry = registry or default_registry
    try:
        parser = selected_registry.get_parser(
            extension=stored_file.extension,
            mime_type=stored_file.mime_type,
        )
    except ParserError as exc:
        raise ResourceValidationError(
            "Stored file MIME type and extension do not select "
            "the same supported parser"
        ) from exc
    return parser


def _provider_for_stored_file(
    stored_file: StoredFile,
    provider: AbstractStorageProvider | None,
) -> AbstractStorageProvider:
    resolved = provider or get_default_storage_provider()
    if resolved.provider_type.value != stored_file.storage_provider:
        raise ResourceValidationError(
            "Configured storage provider does not own the stored file"
        )
    return resolved


def load_stored_file_content(
    stored_file: StoredFile,
    *,
    provider: AbstractStorageProvider | None = None,
    settings: Settings | None = None,
) -> bytes:
    configured = settings or get_settings()
    resolved_provider = _provider_for_stored_file(stored_file, provider)
    try:
        if not resolved_provider.exists(stored_file.storage_path):
            raise ResourceValidationError(
                "Stored file object does not exist"
            )
        current_size = resolved_provider.size(stored_file.storage_path)
        if current_size != stored_file.size_bytes:
            raise ResourceValidationError(
                "Stored file size does not match its registry metadata"
            )
        if current_size > configured.max_upload_size:
            raise ResourceValidationError(
                "Stored file exceeds the configured parser size limit"
            )
        digest = sha256()
        content = bytearray()
        with resolved_provider.open(stored_file.storage_path) as stream:
            while True:
                chunk = stream.read(min(1024 * 1024, configured.max_upload_size + 1))
                if not isinstance(chunk, bytes):
                    raise ResourceValidationError(
                        "Storage provider returned a non-binary stream"
                    )
                if not chunk:
                    break
                content.extend(chunk)
                digest.update(chunk)
                if len(content) > configured.max_upload_size:
                    raise ResourceValidationError(
                        "Stored file exceeds the configured parser size limit"
                    )
    except ResourceValidationError:
        raise
    except (KeyError, OSError, ValueError) as exc:
        raise ResourceValidationError(
            "Stored file object could not be read safely"
        ) from exc
    if len(content) != stored_file.size_bytes:
        raise ResourceValidationError(
            "Stored file size changed while it was being read"
        )
    if digest.hexdigest() != stored_file.sha256.casefold():
        raise ResourceValidationError(
            "Stored file failed SHA-256 integrity verification"
        )
    return bytes(content)


def _resolve_job(
    db: Session,
    stored_file: StoredFile,
    ingestion_job_id: int | None,
) -> IngestionJob:
    version = db.get(DocumentVersion, stored_file.document_version_id)
    if version is None:
        raise ResourceValidationError(
            "Stored file has no valid linked document version"
        )
    if ingestion_job_id is None:
        job = db.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.document_id == version.document_id,
                IngestionJob.status.in_(_PIPELINE_JOB_STATUSES),
            )
            .order_by(desc(IngestionJob.id))
            .limit(1)
        )
        if job is None:
            raise ResourceValidationError(
                "Stored file parsing requires a reserved or running "
                "ingestion job"
            )
        ingestion_job_id = job.id
    job = ingestion_service.get_job(db, ingestion_job_id)
    if job.document_id != version.document_id:
        raise ResourceValidationError(
            "Ingestion job does not belong to the stored file document"
        )
    if job.status not in _PIPELINE_JOB_STATUSES:
        raise ResourceValidationError(
            "Ingestion job must be reserved or running before parsing"
        )
    reservation = job.current_reservation
    if reservation is None:
        raise ResourceValidationError(
            "Ingestion job has no active reservation"
        )
    now = utc_now()
    expires_at = reservation.expires_at
    comparable_now = (
        now.replace(tzinfo=None)
        if expires_at.tzinfo is None
        else now.replace(tzinfo=timezone.utc)
    )
    if expires_at <= comparable_now:
        raise ResourceValidationError(
            "Ingestion job reservation has expired"
        )
    if not reservation.node.active:
        raise ResourceValidationError(
            "Ingestion processing node is not active"
        )
    return job


def validate_stored_file_for_parsing(
    db: Session,
    file_id: int,
    *,
    ingestion_job_id: int | None = None,
    provider: AbstractStorageProvider | None = None,
    registry: ParserRegistry | None = None,
    settings: Settings | None = None,
    inspect_storage: bool = True,
) -> StoredFile:
    stored_file = get_file(db, file_id)
    version = db.get(DocumentVersion, stored_file.document_version_id)
    if version is None:
        raise ResourceValidationError(
            "Stored file has no valid linked document version"
        )
    if not version.is_current:
        raise ResourceValidationError(
            "Stored file document version is not current"
        )
    if not version.checksum.strip():
        raise ResourceValidationError(
            "Stored file document version has no checksum"
        )
    select_parser_for_stored_file(stored_file, registry=registry)
    validate_ingestion_eligibility(db, version.document_id)
    _resolve_job(db, stored_file, ingestion_job_id)
    if inspect_storage:
        resolved_provider = _provider_for_stored_file(stored_file, provider)
        configured = settings or get_settings()
        try:
            if not resolved_provider.exists(stored_file.storage_path):
                raise ResourceValidationError(
                    "Stored file object does not exist"
                )
            if resolved_provider.size(stored_file.storage_path) > (
                configured.max_upload_size
            ):
                raise ResourceValidationError(
                    "Stored file exceeds the configured parser size limit"
                )
        except ResourceValidationError:
            raise
        except (KeyError, OSError, ValueError) as exc:
            raise ResourceValidationError(
                "Stored file object could not be inspected safely"
            ) from exc
    return stored_file


def persist_parse_result(
    db: Session,
    execution_id: int,
    canonical_document,
) -> ParseResult:
    result = parse_result_service.complete_parse_execution(
        db,
        execution_id,
        canonical_document,
        commit=False,
    )
    if result.artifacts:
        db.commit()
        return parse_result_service.get_parse_result(db, result.id)
    parse_result_service.add_parse_artifact(
        db,
        result.id,
        ParseArtifactType.CANONICAL_MANIFEST,
        "canonical-manifest",
        mime_type="application/json",
        content_json={
            "schema_version": result.canonical_schema_version,
            "parser_name": result.parser_name,
            "parser_version": result.parser_version,
            "input_sha256": result.input_sha256,
            "content_hash": result.content_hash,
        },
        commit=False,
    )
    parse_result_service.add_parse_artifact(
        db,
        result.id,
        ParseArtifactType.METADATA,
        "extracted-metadata",
        mime_type="application/json",
        content_json=canonical_document.metadata.model_dump(mode="json"),
        commit=False,
    )
    parse_result_service.add_parse_artifact(
        db,
        result.id,
        ParseArtifactType.STATISTICS,
        "structural-statistics",
        mime_type="application/json",
        content_json=canonical_document.statistics.model_dump(mode="json"),
        commit=False,
    )
    warnings = canonical_document.metadata.properties.get("warnings", [])
    if isinstance(warnings, str):
        warnings = [warnings]
    for warning_index, warning in enumerate(warnings):
        parse_result_service.add_parse_artifact(
            db,
            result.id,
            ParseArtifactType.WARNING,
            f"parser-warning-{warning_index + 1}",
            mime_type="text/plain",
            content_text=str(warning),
            commit=False,
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(
            "Parse result and artifacts could not be persisted atomically"
        ) from exc
    return parse_result_service.get_parse_result(db, result.id)


def parse_stored_file(
    db: Session,
    file_id: int,
    *,
    ingestion_job_id: int | None = None,
    provider: AbstractStorageProvider | None = None,
    registry: ParserRegistry | None = None,
    settings: Settings | None = None,
) -> ParseResult:
    return _run_pipeline(
        db,
        file_id,
        ingestion_job_id=ingestion_job_id,
        provider=provider,
        registry=registry,
        settings=settings,
        force_execution=False,
    )


def reparse_stored_file(
    db: Session,
    file_id: int,
    *,
    ingestion_job_id: int | None = None,
    provider: AbstractStorageProvider | None = None,
    registry: ParserRegistry | None = None,
    settings: Settings | None = None,
) -> ParseResult:
    return _run_pipeline(
        db,
        file_id,
        ingestion_job_id=ingestion_job_id,
        provider=provider,
        registry=registry,
        settings=settings,
        force_execution=True,
    )


def _run_pipeline(
    db: Session,
    file_id: int,
    *,
    ingestion_job_id: int | None,
    provider: AbstractStorageProvider | None,
    registry: ParserRegistry | None,
    settings: Settings | None,
    force_execution: bool,
) -> ParseResult:
    stored_file = validate_stored_file_for_parsing(
        db,
        file_id,
        ingestion_job_id=ingestion_job_id,
        provider=provider,
        registry=registry,
        settings=settings,
        inspect_storage=False,
    )
    parser = select_parser_for_stored_file(stored_file, registry=registry)
    job = _resolve_job(db, stored_file, ingestion_job_id)
    execution = None
    result = None
    if job.status == JobStatus.RESERVED.value:
        job = ingestion_service.start_job(db, job.id)
    try:
        content = load_stored_file_content(
            stored_file,
            provider=provider,
            settings=settings,
        )
        result = parse_result_service.create_or_get_parse_result(
            db,
            stored_file.id,
            parser.parser_name(),
            parser.parser_version(),
            document_version_id=stored_file.document_version_id,
            ingestion_job_id=job.id,
            input_sha256=stored_file.sha256,
        )
        if (
            result.status == ParseResultStatus.SUCCEEDED.value
            and not force_execution
        ):
            ingestion_service.complete_job(db, job.id)
            return result
        execution = parse_result_service.begin_parse_execution(
            db,
            result.id,
            node_name=job.current_reservation.node.node_name,
            allow_succeeded=force_execution,
        )
        document = parser.parse(
            content,
            filename=stored_file.original_filename,
            mime_type=stored_file.mime_type,
        )
        validate_document(document)
        result = persist_parse_result(db, execution.id, document)
        ingestion_service.complete_job(db, job.id)
        return result
    except Exception as exc:
        safe_message = _public_failure_message(exc)
        if execution is not None:
            try:
                parse_result_service.fail_parse_execution(
                    db,
                    execution.id,
                    error_code=type(exc).__name__,
                    error_message=safe_message,
                )
            except (ResourceConflictError, ResourceNotFoundError):
                db.rollback()
        try:
            current_job = ingestion_service.get_job(db, job.id)
            if current_job.status == JobStatus.RUNNING.value:
                ingestion_service.fail_job(
                    db,
                    current_job.id,
                    safe_message,
                )
        except ServiceError:
            db.rollback()
        if isinstance(exc, ServiceError):
            raise
        if isinstance(exc, ParserError):
            raise ResourceValidationError(str(exc)) from exc
        raise ResourceValidationError(
            "Stored file parsing failed safely"
        ) from exc


def get_parse_readiness(
    db: Session,
    file_id: int,
    *,
    ingestion_job_id: int | None = None,
    provider: AbstractStorageProvider | None = None,
    registry: ParserRegistry | None = None,
    settings: Settings | None = None,
) -> ParseReadinessRead:
    stored_file = get_file(db, file_id)
    configured = settings or get_settings()
    reasons: list[str] = []
    parser_name = None
    parser_version = None
    storage_exists = False
    size_within_limit = False
    mime_extension_match = False
    document_version_valid = False
    ingestion_eligible = False
    job = None
    try:
        parser = select_parser_for_stored_file(
            stored_file,
            registry=registry,
        )
        parser_name = parser.parser_name()
        parser_version = parser.parser_version()
        mime_extension_match = True
    except ResourceValidationError as exc:
        reasons.append(exc.detail)
    version = db.get(DocumentVersion, stored_file.document_version_id)
    if version is None:
        reasons.append("Stored file has no valid linked document version")
    elif not version.is_current or not version.checksum.strip():
        reasons.append("Stored file document version is not current and valid")
    else:
        document_version_valid = True
        try:
            validate_ingestion_eligibility(db, version.document_id)
            ingestion_eligible = True
        except ResourceValidationError as exc:
            reasons.append(exc.detail)
    try:
        resolved_provider = _provider_for_stored_file(stored_file, provider)
        storage_exists = resolved_provider.exists(stored_file.storage_path)
        if not storage_exists:
            reasons.append("Stored file object does not exist")
        else:
            size_within_limit = (
                resolved_provider.size(stored_file.storage_path)
                == stored_file.size_bytes
                and stored_file.size_bytes <= configured.max_upload_size
            )
            if not size_within_limit:
                reasons.append(
                    "Stored file size is invalid for parsing"
                )
    except (KeyError, OSError, ValueError, ResourceValidationError):
        reasons.append("Stored file object could not be inspected safely")
    try:
        job = _resolve_job(db, stored_file, ingestion_job_id)
    except ResourceValidationError as exc:
        reasons.append(exc.detail)
    return ParseReadinessRead(
        file_id=stored_file.id,
        ready=not reasons,
        reasons=list(dict.fromkeys(reasons)),
        parser_name=parser_name,
        parser_version=parser_version,
        ingestion_job_id=job.id if job is not None else ingestion_job_id,
        ingestion_status=job.status if job is not None else None,
        storage_exists=storage_exists,
        size_within_limit=size_within_limit,
        mime_extension_match=mime_extension_match,
        document_version_valid=document_version_valid,
        ingestion_eligible=ingestion_eligible,
    )


def _public_failure_message(exc: Exception) -> str:
    if isinstance(exc, ServiceError):
        return exc.detail[:2000]
    if isinstance(exc, ParserError):
        return str(exc)[:2000]
    return "Stored file parsing failed safely"


__all__ = [
    "get_parse_readiness",
    "load_stored_file_content",
    "parse_stored_file",
    "persist_parse_result",
    "reparse_stored_file",
    "select_parser_for_stored_file",
    "validate_stored_file_for_parsing",
]
