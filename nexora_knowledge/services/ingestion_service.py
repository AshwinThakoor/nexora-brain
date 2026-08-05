from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import (
    AttemptStatus,
    AuditEventType,
    Document,
    IngestionAttempt,
    IngestionAuditEvent,
    IngestionJob,
    JobReservation,
    JobStatus,
    ProcessingNode,
)
from ..models.common import utc_now
from . import document_service
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


ACTIVE_JOB_STATUSES = frozenset(
    {
        JobStatus.NEW.value,
        JobStatus.QUEUED.value,
        JobStatus.RESERVED.value,
        JobStatus.RUNNING.value,
        JobStatus.FAILED.value,
        JobStatus.RETRYING.value,
    }
)
LEGAL_TRANSITIONS = {
    JobStatus.NEW.value: {
        JobStatus.QUEUED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.QUEUED.value: {
        JobStatus.RESERVED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.RESERVED.value: {
        JobStatus.QUEUED.value,
        JobStatus.RUNNING.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.RUNNING.value: {
        JobStatus.SUCCEEDED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.FAILED.value: {
        JobStatus.RETRYING.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.RETRYING.value: {
        JobStatus.RESERVED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.SUCCEEDED.value: set(),
    JobStatus.CANCELLED.value: set(),
}
_SORT_COLUMNS = {
    "id": IngestionJob.id,
    "uuid": IngestionJob.uuid,
    "document_id": IngestionJob.document_id,
    "status": IngestionJob.status,
    "priority": IngestionJob.priority,
    "created_at": IngestionJob.created_at,
    "updated_at": IngestionJob.updated_at,
    "completed_at": IngestionJob.completed_at,
}


def _job_query():
    return (
        select(IngestionJob)
        .options(
            selectinload(IngestionJob.document),
            selectinload(IngestionJob.attempts),
            selectinload(IngestionJob.audit_events),
            selectinload(IngestionJob.reservations).selectinload(
                JobReservation.node
            ),
        )
        .execution_options(populate_existing=True)
    )


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def get_job(db: Session, job_id: int) -> IngestionJob:
    job = db.scalar(_job_query().where(IngestionJob.id == job_id))
    if job is None:
        raise ResourceNotFoundError("Ingestion job", job_id)
    return job


def _locked_job(db: Session, job_id: int) -> IngestionJob:
    job = db.scalar(
        select(IngestionJob)
        .where(IngestionJob.id == job_id)
        .with_for_update()
    )
    if job is None:
        raise ResourceNotFoundError("Ingestion job", job_id)
    return job


def _normalize_status(status: JobStatus | str) -> str:
    try:
        return JobStatus(str(status).strip().casefold()).value
    except ValueError as exc:
        raise ResourceValidationError("Unsupported ingestion job status") from exc


def record_audit_event(
    db: Session,
    job_id: int,
    event_type: AuditEventType | str,
    previous_status: JobStatus | str | None,
    new_status: JobStatus | str,
    *,
    reason: str | None = None,
    commit: bool = True,
) -> IngestionAuditEvent:
    if db.get(IngestionJob, job_id) is None:
        raise ResourceNotFoundError("Ingestion job", job_id)
    try:
        normalized_event = AuditEventType(
            str(event_type).strip().casefold()
        ).value
    except ValueError as exc:
        raise ResourceValidationError(
            "Unsupported ingestion audit event type"
        ) from exc
    normalized_previous = (
        None if previous_status is None else _normalize_status(previous_status)
    )
    normalized_new = _normalize_status(new_status)
    normalized_reason = reason.strip() if isinstance(reason, str) else reason
    event = IngestionAuditEvent(
        job_id=job_id,
        event_type=normalized_event,
        previous_status=normalized_previous,
        new_status=normalized_new,
        reason=normalized_reason or None,
    )
    db.add(event)
    if commit:
        _commit(db, "Ingestion audit event could not be recorded")
        db.refresh(event)
    else:
        db.flush()
    return event


def _transition(
    db: Session,
    job: IngestionJob,
    new_status: JobStatus | str,
    event_type: AuditEventType | str,
    *,
    reason: str | None = None,
) -> None:
    normalized_new = _normalize_status(new_status)
    allowed = LEGAL_TRANSITIONS.get(job.status, set())
    if normalized_new not in allowed:
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> {normalized_new}"
        )
    previous = job.status
    job.status = normalized_new
    if normalized_new in {
        JobStatus.SUCCEEDED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    }:
        job.completed_at = utc_now()
    else:
        job.completed_at = None
    record_audit_event(
        db,
        job.id,
        event_type,
        previous,
        normalized_new,
        reason=reason,
        commit=False,
    )


def create_job(db: Session, values: Mapping[str, Any]) -> IngestionJob:
    try:
        document_id = int(values["document_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ResourceValidationError(
            "Document ID is required for an ingestion job"
        ) from exc
    try:
        priority = int(values.get("priority", 100))
    except (TypeError, ValueError) as exc:
        raise ResourceValidationError(
            "Ingestion priority must be an integer"
        ) from exc
    if not 0 <= priority <= 1000:
        raise ResourceValidationError(
            "Ingestion priority must be between 0 and 1000"
        )

    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
    )
    if document is None:
        raise ResourceNotFoundError("Document", document_id)
    existing = db.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.document_id == document_id,
            IngestionJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(desc(IngestionJob.id))
        .limit(1)
    )
    if existing is not None:
        existing_id = existing.id
        db.commit()
        return get_job(db, existing_id)

    job = IngestionJob(
        document_id=document_id,
        status=JobStatus.NEW.value,
        priority=priority,
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        job.id,
        AuditEventType.CREATED,
        None,
        JobStatus.NEW,
        commit=False,
    )
    _commit(db, "An active ingestion job already exists")
    return get_job(db, job.id)


def queue_job(db: Session, job_id: int) -> IngestionJob:
    job = _locked_job(db, job_id)
    document_service.validate_ingestion_eligibility(db, job.document_id)
    _transition(
        db,
        job,
        JobStatus.QUEUED,
        AuditEventType.QUEUED,
    )
    _commit(db, "Ingestion job could not be queued")
    return get_job(db, job.id)


def register_processing_node(
    db: Session,
    values: Mapping[str, Any],
) -> ProcessingNode:
    node_name = str(values.get("node_name", "")).strip()
    node_version = str(values.get("node_version", "")).strip()
    hostname = str(values.get("hostname", "")).strip()
    if not node_name or len(node_name) > 255:
        raise ResourceValidationError(
            "Processing node name must contain between 1 and 255 characters"
        )
    if not node_version or len(node_version) > 100:
        raise ResourceValidationError(
            "Processing node version must contain between 1 and 100 characters"
        )
    if not hostname or len(hostname) > 255:
        raise ResourceValidationError(
            "Processing node hostname must contain between 1 and 255 characters"
        )
    node = db.scalar(
        select(ProcessingNode)
        .where(func.lower(ProcessingNode.node_name) == node_name.casefold())
        .with_for_update()
    )
    heartbeat = utc_now()
    if node is None:
        node = ProcessingNode(
            node_name=node_name,
            node_version=node_version,
            hostname=hostname,
            last_heartbeat=heartbeat,
            active=bool(values.get("active", True)),
        )
        db.add(node)
    else:
        node.node_version = node_version
        node.hostname = hostname
        node.last_heartbeat = heartbeat
        node.active = bool(values.get("active", True))
    _commit(db, "Processing node name already exists")
    db.refresh(node)
    return node


def heartbeat_node(db: Session, node_id: int) -> ProcessingNode:
    node = db.scalar(
        select(ProcessingNode)
        .where(ProcessingNode.id == node_id)
        .with_for_update()
    )
    if node is None:
        raise ResourceNotFoundError("Processing node", node_id)
    node.last_heartbeat = utc_now()
    node.active = True
    _commit(db, "Processing node heartbeat could not be recorded")
    db.refresh(node)
    return node


def list_processing_nodes(
    db: Session,
    *,
    active: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[ProcessingNode], int]:
    if offset < 0 or not 1 <= limit <= 200:
        raise ResourceValidationError(
            "Processing node pagination values are invalid"
        )
    filters = []
    if active is not None:
        filters.append(ProcessingNode.active.is_(active))
    total = db.scalar(
        select(func.count()).select_from(ProcessingNode).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(ProcessingNode)
            .where(*filters)
            .order_by(ProcessingNode.node_name, ProcessingNode.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def _active_reservation(
    db: Session,
    job_id: int,
    *,
    for_update: bool = False,
) -> JobReservation | None:
    statement = select(JobReservation).where(
        JobReservation.job_id == job_id,
        JobReservation.active_slot.is_(True),
        JobReservation.released_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def reserve_job(
    db: Session,
    job_id: int,
    node_id: int,
    *,
    ttl_seconds: int = 300,
) -> IngestionJob:
    if not 1 <= ttl_seconds <= 86400:
        raise ResourceValidationError(
            "Reservation TTL must be between 1 and 86400 seconds"
        )
    job = _locked_job(db, job_id)
    node = db.get(ProcessingNode, node_id)
    if node is None:
        raise ResourceNotFoundError("Processing node", node_id)
    if not node.active:
        raise ResourceValidationError("Processing node is not active")
    if _active_reservation(db, job.id, for_update=True) is not None:
        raise ResourceConflictError(
            "Ingestion job already has an active reservation"
        )
    if job.status not in {
        JobStatus.QUEUED.value,
        JobStatus.RETRYING.value,
    }:
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> reserved"
        )
    reserved_at = utc_now()
    reservation = JobReservation(
        job_id=job.id,
        node_id=node.id,
        reserved_at=reserved_at,
        expires_at=reserved_at + timedelta(seconds=ttl_seconds),
        active_slot=True,
    )
    db.add(reservation)
    _transition(
        db,
        job,
        JobStatus.RESERVED,
        AuditEventType.RESERVED,
        reason=f"Reserved by processing node {node.node_name}",
    )
    _commit(db, "Ingestion job already has an active reservation")
    return get_job(db, job.id)


def release_job(
    db: Session,
    job_id: int,
    *,
    reason: str | None = None,
) -> IngestionJob:
    job = _locked_job(db, job_id)
    reservation = _active_reservation(db, job.id, for_update=True)
    if reservation is None:
        raise ResourceValidationError(
            "Ingestion job has no active reservation"
        )
    if job.status != JobStatus.RESERVED.value:
        raise ResourceValidationError(
            "Only a reserved job can be explicitly released"
        )
    reservation.released_at = utc_now()
    reservation.active_slot = False
    _transition(
        db,
        job,
        JobStatus.QUEUED,
        AuditEventType.RELEASED,
        reason=reason or "Reservation released",
    )
    _commit(db, "Ingestion reservation could not be released")
    return get_job(db, job.id)


def start_job(db: Session, job_id: int) -> IngestionJob:
    job = _locked_job(db, job_id)
    if job.status != JobStatus.RESERVED.value:
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> running"
        )
    reservation = _active_reservation(db, job.id, for_update=True)
    now = utc_now()
    if reservation is None:
        raise ResourceValidationError(
            "Ingestion job must have an active reservation before starting"
        )
    if reservation.expires_at <= _matching_timezone(
        now,
        reservation.expires_at,
    ):
        raise ResourceValidationError(
            "Ingestion job reservation has expired"
        )
    _transition(
        db,
        job,
        JobStatus.RUNNING,
        AuditEventType.STARTED,
    )
    last_number = db.scalar(
        select(func.max(IngestionAttempt.attempt_number)).where(
            IngestionAttempt.job_id == job.id
        )
    ) or 0
    db.add(
        IngestionAttempt(
            job_id=job.id,
            attempt_number=last_number + 1,
            started_at=now,
            status=AttemptStatus.RUNNING.value,
        )
    )
    job.last_error = None
    _commit(db, "Ingestion attempt could not be started")
    return get_job(db, job.id)


def _matching_timezone(value: datetime, reference: datetime) -> datetime:
    if reference.tzinfo is None and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if reference.tzinfo is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _running_attempt(db: Session, job_id: int) -> IngestionAttempt:
    attempt = db.scalar(
        select(IngestionAttempt)
        .where(
            IngestionAttempt.job_id == job_id,
            IngestionAttempt.status == AttemptStatus.RUNNING.value,
            IngestionAttempt.finished_at.is_(None),
        )
        .order_by(desc(IngestionAttempt.attempt_number))
        .limit(1)
        .with_for_update()
    )
    if attempt is None:
        raise ResourceValidationError(
            "Running ingestion job has no active attempt"
        )
    return attempt


def _finish_attempt(
    attempt: IngestionAttempt,
    status: AttemptStatus | str,
    *,
    error_message: str | None = None,
) -> None:
    finished_at = utc_now()
    started_at = attempt.started_at
    comparable_finished = _matching_timezone(finished_at, started_at)
    attempt.finished_at = finished_at
    attempt.status = str(status).casefold()
    attempt.error_message = error_message
    attempt.duration_ms = max(
        0,
        int((comparable_finished - started_at).total_seconds() * 1000),
    )


def _release_active_reservation(
    db: Session,
    job: IngestionJob,
    *,
    reason: str,
) -> None:
    reservation = _active_reservation(db, job.id, for_update=True)
    if reservation is None:
        return
    reservation.released_at = utc_now()
    reservation.active_slot = False
    record_audit_event(
        db,
        job.id,
        AuditEventType.RELEASED,
        job.status,
        job.status,
        reason=reason,
        commit=False,
    )


def complete_job(db: Session, job_id: int) -> IngestionJob:
    job = _locked_job(db, job_id)
    if job.status != JobStatus.RUNNING.value:
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> succeeded"
        )
    attempt = _running_attempt(db, job.id)
    _finish_attempt(attempt, AttemptStatus.SUCCESS)
    _transition(
        db,
        job,
        JobStatus.SUCCEEDED,
        AuditEventType.SUCCEEDED,
    )
    job.last_error = None
    _release_active_reservation(
        db,
        job,
        reason="Reservation released after successful completion",
    )
    _commit(db, "Ingestion job could not be completed")
    return get_job(db, job.id)


def fail_job(
    db: Session,
    job_id: int,
    error_message: str,
) -> IngestionJob:
    normalized_error = error_message.strip()
    if not normalized_error:
        raise ResourceValidationError("Ingestion failure reason is required")
    job = _locked_job(db, job_id)
    if job.status != JobStatus.RUNNING.value:
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> failed"
        )
    attempt = _running_attempt(db, job.id)
    _finish_attempt(
        attempt,
        AttemptStatus.FAILED,
        error_message=normalized_error,
    )
    job.last_error = normalized_error
    _transition(
        db,
        job,
        JobStatus.FAILED,
        AuditEventType.FAILED,
        reason=normalized_error,
    )
    _release_active_reservation(
        db,
        job,
        reason="Reservation released after failed attempt",
    )
    _commit(db, "Ingestion job failure could not be recorded")
    return get_job(db, job.id)


def retry_job(
    db: Session,
    job_id: int,
    *,
    retry_limit: int | None = None,
) -> IngestionJob:
    limit = (
        get_settings().ingestion_retry_limit
        if retry_limit is None
        else retry_limit
    )
    if not 0 <= limit <= 100:
        raise ResourceValidationError(
            "Retry limit must be between 0 and 100"
        )
    job = _locked_job(db, job_id)
    if job.status != JobStatus.FAILED.value:
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> retrying"
        )
    retries_used = db.scalar(
        select(func.count())
        .select_from(IngestionAuditEvent)
        .where(
            IngestionAuditEvent.job_id == job.id,
            IngestionAuditEvent.event_type == AuditEventType.RETRIED.value,
        )
    ) or 0
    if retries_used >= limit:
        raise ResourceValidationError(
            f"Ingestion retry limit of {limit} has been reached"
        )
    _transition(
        db,
        job,
        JobStatus.RETRYING,
        AuditEventType.RETRIED,
        reason=f"Retry {retries_used + 1} of {limit}",
    )
    _commit(db, "Ingestion retry could not be scheduled")
    return get_job(db, job.id)


def cancel_job(
    db: Session,
    job_id: int,
    *,
    reason: str | None = None,
) -> IngestionJob:
    job = _locked_job(db, job_id)
    if JobStatus.CANCELLED.value not in LEGAL_TRANSITIONS.get(
        job.status,
        set(),
    ):
        raise ResourceValidationError(
            f"Invalid ingestion transition: {job.status} -> cancelled"
        )
    normalized_reason = reason.strip() if isinstance(reason, str) else None
    if job.status == JobStatus.RUNNING.value:
        attempt = _running_attempt(db, job.id)
        _finish_attempt(
            attempt,
            AttemptStatus.FAILED,
            error_message=normalized_reason or "Ingestion job cancelled",
        )
    _transition(
        db,
        job,
        JobStatus.CANCELLED,
        AuditEventType.CANCELLED,
        reason=normalized_reason or "Ingestion job cancelled",
    )
    _release_active_reservation(
        db,
        job,
        reason="Reservation released after cancellation",
    )
    _commit(db, "Ingestion job could not be cancelled")
    return get_job(db, job.id)


def cleanup_expired_reservations(
    db: Session,
    *,
    as_of: datetime | None = None,
) -> int:
    now = as_of or utc_now()
    reservations = list(
        db.scalars(
            select(JobReservation)
            .where(
                JobReservation.active_slot.is_(True),
                JobReservation.released_at.is_(None),
                JobReservation.expires_at <= now,
            )
            .order_by(JobReservation.id)
            .with_for_update()
        )
    )
    for reservation in reservations:
        job = _locked_job(db, reservation.job_id)
        reservation.released_at = now
        reservation.active_slot = False
        if job.status == JobStatus.RESERVED.value:
            _transition(
                db,
                job,
                JobStatus.QUEUED,
                AuditEventType.RELEASED,
                reason="Reservation expired before processing started",
            )
        elif job.status == JobStatus.RUNNING.value:
            attempt = _running_attempt(db, job.id)
            message = "Reservation expired while processing was running"
            _finish_attempt(
                attempt,
                AttemptStatus.FAILED,
                error_message=message,
            )
            job.last_error = message
            _transition(
                db,
                job,
                JobStatus.FAILED,
                AuditEventType.FAILED,
                reason=message,
            )
            record_audit_event(
                db,
                job.id,
                AuditEventType.RELEASED,
                job.status,
                job.status,
                reason="Expired reservation released",
                commit=False,
            )
        else:
            record_audit_event(
                db,
                job.id,
                AuditEventType.RELEASED,
                job.status,
                job.status,
                reason="Expired reservation released",
                commit=False,
            )
    if reservations:
        _commit(db, "Expired ingestion reservations could not be cleaned up")
    return len(reservations)


def list_jobs(
    db: Session,
    *,
    status: JobStatus | str | None = None,
    document_id: int | None = None,
    priority: int | None = None,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[IngestionJob], int]:
    return search_jobs(
        db,
        status=status,
        document_id=document_id,
        priority=priority,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def search_jobs(
    db: Session,
    *,
    q: str | None = None,
    status: JobStatus | str | None = None,
    document_id: int | None = None,
    priority: int | None = None,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[IngestionJob], int]:
    if offset < 0 or not 1 <= limit <= 200:
        raise ResourceValidationError(
            "Ingestion job pagination values are invalid"
        )
    sort_column = _SORT_COLUMNS.get(sort_by)
    if sort_column is None:
        raise ResourceValidationError("Unsupported ingestion job sort field")
    if sort_order not in {"asc", "desc"}:
        raise ResourceValidationError(
            "Ingestion job sort order must be 'asc' or 'desc'"
        )
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                IngestionJob.uuid.ilike(pattern),
                IngestionJob.last_error.ilike(pattern),
                IngestionJob.document.has(
                    or_(
                        Document.title.ilike(pattern),
                        Document.slug.ilike(pattern),
                    )
                ),
            )
        )
    if status is not None:
        filters.append(IngestionJob.status == _normalize_status(status))
    if document_id is not None:
        filters.append(IngestionJob.document_id == document_id)
    if priority is not None:
        filters.append(IngestionJob.priority == priority)

    total = db.scalar(
        select(func.count()).select_from(IngestionJob).where(*filters)
    ) or 0
    order_expression = (
        asc(sort_column) if sort_order == "asc" else desc(sort_column)
    )
    items = list(
        db.scalars(
            select(IngestionJob)
            .where(*filters)
            .order_by(order_expression, IngestionJob.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def get_audit_history(
    db: Session,
    job_id: int,
) -> list[IngestionAuditEvent]:
    get_job(db, job_id)
    return list(
        db.scalars(
            select(IngestionAuditEvent)
            .where(IngestionAuditEvent.job_id == job_id)
            .order_by(IngestionAuditEvent.id)
        )
    )


__all__ = [
    "ACTIVE_JOB_STATUSES",
    "LEGAL_TRANSITIONS",
    "cancel_job",
    "cleanup_expired_reservations",
    "complete_job",
    "create_job",
    "fail_job",
    "get_audit_history",
    "get_job",
    "heartbeat_node",
    "list_jobs",
    "list_processing_nodes",
    "queue_job",
    "record_audit_event",
    "register_processing_node",
    "release_job",
    "reserve_job",
    "retry_job",
    "search_jobs",
    "start_job",
]
