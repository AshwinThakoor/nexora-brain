from __future__ import annotations

from datetime import datetime
import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from ..models import AcademyRole, ParseResult
from ..schemas.parse_result import (
    ParseArtifactRead,
    ParseHistoryRead,
    ParseReadinessRead,
    ParseRequest,
    ParseResultRead,
    ParseResultSearch,
    ParseResultSummary,
    ReparseRequest,
)
from ..services import parse_result_service, parser_pipeline_service
from ..services.authorization import (
    Principal,
    require_parse_history_reader,
    require_parse_result_reader,
    require_parser_admin,
)
from .dependencies import get_current_principal, get_db


file_router = APIRouter(
    prefix="/api/v1/files",
    tags=["persistent-parser-results"],
)
router = APIRouter(
    prefix="/api/v1/parse-results",
    tags=["persistent-parser-results"],
)


@file_router.post("/{file_id}/parse", response_model=ParseResultRead)
def parse_file(
    file_id: int,
    payload: Annotated[ParseRequest, Body()],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    result = parser_pipeline_service.parse_stored_file(
        db,
        file_id,
        ingestion_job_id=payload.ingestion_job_id,
    )
    return _read_payload(result, include_canonical=True, include_related=True)


@file_router.post("/{file_id}/reparse", response_model=ParseResultRead)
def reparse_file(
    file_id: int,
    payload: Annotated[ReparseRequest, Body()],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    result = parser_pipeline_service.reparse_stored_file(
        db,
        file_id,
        ingestion_job_id=payload.ingestion_job_id,
    )
    return _read_payload(result, include_canonical=True, include_related=True)


@file_router.get(
    "/{file_id}/parse-readiness",
    response_model=ParseReadinessRead,
)
def parse_readiness(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    ingestion_job_id: int | None = None,
):
    require_parse_result_reader(principal)
    return parser_pipeline_service.get_parse_readiness(
        db,
        file_id,
        ingestion_job_id=ingestion_job_id,
    )


@file_router.get(
    "/{file_id}/parse-results",
    response_model=ParseResultSearch,
)
def list_file_parse_results(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    document_version_id: int | None = None,
    ingestion_job_id: int | None = None,
    parser_name: str | None = None,
    parser_version: str | None = None,
    status: str | None = None,
    input_sha256: str | None = None,
    content_hash: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    offset: Annotated[int, Query(ge=0)] = 0,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    require_parse_result_reader(principal)
    items, total = parse_result_service.list_parse_results(
        db,
        stored_file_id=file_id,
        document_version_id=document_version_id,
        ingestion_job_id=ingestion_job_id,
        parser_name=parser_name,
        parser_version=parser_version,
        status=status,
        input_sha256=input_sha256,
        content_hash=content_hash,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        skip=skip,
        limit=limit,
    )
    effective_offset = offset if skip is None else skip
    return ParseResultSearch(
        items=[ParseResultSummary.model_validate(item) for item in items],
        total=total,
        offset=effective_offset,
        skip=effective_offset,
        limit=limit,
    )


@router.get("/{result_id}", response_model=ParseResultRead)
def read_parse_result(
    result_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parse_result_reader(principal)
    result = parse_result_service.get_parse_result(db, result_id)
    is_admin = principal.role == AcademyRole.ADMIN
    is_reviewer = principal.role in {
        AcademyRole.REVIEWER,
        AcademyRole.ADMIN,
    }
    return _read_payload(
        result,
        include_canonical=is_admin,
        include_related=is_reviewer,
    )


@router.get("/{result_id}/history", response_model=ParseHistoryRead)
def read_parse_history(
    result_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parse_history_reader(principal)
    result = parse_result_service.get_parse_result(db, result_id)
    executions = parse_result_service.get_parse_history(db, result_id)
    return ParseHistoryRead(
        result=ParseResultSummary.model_validate(result),
        executions=executions,
    )


@router.get(
    "/{result_id}/artifacts",
    response_model=list[ParseArtifactRead],
)
def read_parse_artifacts(
    result_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    return parse_result_service.get_parse_result(db, result_id).artifacts


@router.post("/{result_id}/invalidate", response_model=ParseResultRead)
def invalidate_result(
    result_id: int,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    result = parse_result_service.invalidate_parse_result(db, result_id)
    return _read_payload(result, include_canonical=True, include_related=True)


def _read_payload(
    result: ParseResult,
    *,
    include_canonical: bool,
    include_related: bool,
) -> ParseResultRead:
    canonical = None
    if include_canonical and result.canonical_json:
        canonical = json.loads(result.canonical_json)
    summary = ParseResultSummary.model_validate(result)
    return ParseResultRead(
        **summary.model_dump(),
        canonical_json=canonical,
        canonical_document=canonical,
        statistics_json=result.statistics_json,
        metadata_json=result.metadata_json,
        executions=result.executions if include_related else [],
        artifacts=(
            result.artifacts
            if include_related and include_canonical
            else []
        ),
    )


__all__ = ["file_router", "router"]
