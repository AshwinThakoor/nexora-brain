from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from ..models import JobStatus
from ..schemas import (
    IngestionAuditRead,
    IngestionCancelRequest,
    IngestionFailureRequest,
    IngestionJobCreate,
    IngestionJobRead,
    IngestionJobSearch,
    IngestionRetryRequest,
    JobReservationRequest,
    ProcessingNodeCreate,
    ProcessingNodeRead,
    ProcessingNodeSearch,
)
from ..services import ingestion_service
from ..services.authorization import (
    Principal,
    require_ingestion_admin,
    require_ingestion_reader,
)
from .dependencies import get_current_principal, get_db


router = APIRouter(
    prefix="/api/v1/ingestion/jobs",
    tags=["ingestion-orchestration"],
)
processing_node_router = APIRouter(
    prefix="/api/v1/processing/nodes",
    tags=["ingestion-orchestration"],
)

SortField = Literal[
    "id",
    "uuid",
    "document_id",
    "status",
    "priority",
    "created_at",
    "updated_at",
    "completed_at",
]
SortOrder = Literal["asc", "desc"]


@router.post(
    "",
    response_model=IngestionJobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    request: IngestionJobCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_admin(principal)
    job = ingestion_service.create_job(db, request.model_dump())
    if job.status == JobStatus.NEW.value:
        job = ingestion_service.queue_job(db, job.id)
    return job


@router.get("", response_model=IngestionJobSearch)
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    job_status: Annotated[
        JobStatus | None,
        Query(alias="status"),
    ] = None,
    document_id: Annotated[int | None, Query(gt=0)] = None,
    priority: Annotated[int | None, Query(ge=0, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: SortField = "created_at",
    sort_order: SortOrder = "desc",
):
    require_ingestion_reader(principal)
    resolved_offset = skip if skip is not None else offset
    items, total = ingestion_service.search_jobs(
        db,
        q=q,
        status=job_status,
        document_id=document_id,
        priority=priority,
        offset=resolved_offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return IngestionJobSearch(
        items=items,
        total=total,
        offset=resolved_offset,
        skip=resolved_offset,
        limit=limit,
    )


@router.get("/{job_id}", response_model=IngestionJobRead)
def get_job(
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_reader(principal)
    return ingestion_service.get_job(db, job_id)


@router.post("/{job_id}/reserve", response_model=IngestionJobRead)
def reserve_job(
    request: JobReservationRequest,
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_admin(principal)
    return ingestion_service.reserve_job(
        db,
        job_id,
        request.node_id,
        ttl_seconds=request.ttl_seconds,
    )


@router.post("/{job_id}/start", response_model=IngestionJobRead)
def start_job(
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_admin(principal)
    return ingestion_service.start_job(db, job_id)


@router.post("/{job_id}/complete", response_model=IngestionJobRead)
def complete_job(
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_admin(principal)
    return ingestion_service.complete_job(db, job_id)


@router.post("/{job_id}/fail", response_model=IngestionJobRead)
def fail_job(
    request: IngestionFailureRequest,
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_admin(principal)
    return ingestion_service.fail_job(
        db,
        job_id,
        request.error_message,
    )


@router.post("/{job_id}/retry", response_model=IngestionJobRead)
def retry_job(
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    request: IngestionRetryRequest | None = None,
):
    require_ingestion_admin(principal)
    return ingestion_service.retry_job(
        db,
        job_id,
        retry_limit=request.retry_limit if request is not None else None,
    )


@router.post("/{job_id}/cancel", response_model=IngestionJobRead)
def cancel_job(
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    request: IngestionCancelRequest | None = None,
):
    require_ingestion_admin(principal)
    return ingestion_service.cancel_job(
        db,
        job_id,
        reason=request.reason if request is not None else None,
    )


@router.get(
    "/{job_id}/audit",
    response_model=list[IngestionAuditRead],
)
def get_audit_history(
    job_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_reader(principal)
    return ingestion_service.get_audit_history(db, job_id)


@processing_node_router.get("", response_model=ProcessingNodeSearch)
def list_processing_nodes(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    active: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    require_ingestion_reader(principal)
    resolved_offset = skip if skip is not None else offset
    items, total = ingestion_service.list_processing_nodes(
        db,
        active=active,
        offset=resolved_offset,
        limit=limit,
    )
    return ProcessingNodeSearch(
        items=items,
        total=total,
        offset=resolved_offset,
        skip=resolved_offset,
        limit=limit,
    )


@processing_node_router.post(
    "",
    response_model=ProcessingNodeRead,
    status_code=status.HTTP_201_CREATED,
)
def register_processing_node(
    request: ProcessingNodeCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_ingestion_admin(principal)
    return ingestion_service.register_processing_node(
        db,
        request.model_dump(),
    )


__all__ = ["processing_node_router", "router"]
