from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from .common import ORMResponse, PositiveId


NodeName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
NodeVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ReasonText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class IngestionJobCreate(ORMResponse):
    document_id: PositiveId
    priority: int = Field(default=100, ge=0, le=1000)


class IngestionAttemptRead(ORMResponse):
    id: int
    job_id: int
    attempt_number: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    error_message: str | None
    duration_ms: int | None


class IngestionAuditRead(ORMResponse):
    id: int
    job_id: int
    event_type: str
    previous_status: str | None
    new_status: str
    reason: str | None
    created_at: datetime


class ProcessingNodeCreate(ORMResponse):
    node_name: NodeName
    node_version: NodeVersion
    hostname: NodeName
    active: bool = True


class ProcessingNodeRead(ORMResponse):
    id: int
    node_name: str
    node_version: str
    hostname: str
    last_heartbeat: datetime
    active: bool


class ProcessingNodeSearch(ORMResponse):
    items: list[ProcessingNodeRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class JobReservationRequest(ORMResponse):
    node_id: PositiveId
    ttl_seconds: int = Field(default=300, ge=1, le=86400)


class JobReservationRead(ORMResponse):
    id: int
    job_id: int
    node_id: int
    reserved_at: datetime
    expires_at: datetime
    released_at: datetime | None
    node: ProcessingNodeRead


class IngestionJobSummary(ORMResponse):
    id: int
    uuid: str
    document_id: int
    status: str
    priority: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    last_error: str | None


class IngestionJobRead(IngestionJobSummary):
    attempts: list[IngestionAttemptRead]
    audit_events: list[IngestionAuditRead]
    reservations: list[JobReservationRead]
    current_reservation: JobReservationRead | None


class IngestionJobSearch(ORMResponse):
    items: list[IngestionJobSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class IngestionFailureRequest(ORMResponse):
    error_message: ReasonText


class IngestionRetryRequest(ORMResponse):
    retry_limit: int | None = Field(default=None, ge=0, le=100)


class IngestionCancelRequest(ORMResponse):
    reason: ReasonText | None = None


__all__ = [
    "IngestionAttemptRead",
    "IngestionAuditRead",
    "IngestionCancelRequest",
    "IngestionFailureRequest",
    "IngestionJobCreate",
    "IngestionJobRead",
    "IngestionJobSearch",
    "IngestionJobSummary",
    "IngestionRetryRequest",
    "JobReservationRead",
    "JobReservationRequest",
    "ProcessingNodeCreate",
    "ProcessingNodeRead",
    "ProcessingNodeSearch",
]
