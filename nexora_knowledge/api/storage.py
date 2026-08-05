from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from ..schemas import StoredFileRead, UploadSessionCreate, UploadSessionRead
from ..services import storage_service
from ..services.authorization import Principal, require_storage_admin
from .dependencies import get_current_principal, get_db


router = APIRouter(
    prefix="/api/v1/uploads",
    tags=["secure-storage"],
)
file_router = APIRouter(
    prefix="/api/v1/files",
    tags=["secure-storage"],
)


@router.post(
    "/session",
    response_model=UploadSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_session(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    request: UploadSessionCreate | None = None,
):
    require_storage_admin(principal)
    return storage_service.create_upload_session(
        db,
        principal.external_id,
        ttl_seconds=request.ttl_seconds if request is not None else None,
    )


@router.post(
    "/{session_id}",
    response_model=UploadSessionRead,
)
async def upload_file(
    session_id: Annotated[int, Path(gt=0)],
    document_version_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_storage_admin(principal)
    try:
        storage_service.store_file(
            db,
            session_id,
            document_version_id,
            file.filename or "",
            file.content_type or "application/octet-stream",
            file.file,
        )
        return storage_service.complete_upload(db, session_id)
    finally:
        await file.close()


@router.get("/{session_id}", response_model=UploadSessionRead)
def get_upload_session(
    session_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_storage_admin(principal)
    return storage_service.get_upload_session(db, session_id)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_upload(
    session_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    require_storage_admin(principal)
    storage_service.cancel_upload(db, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@file_router.get("/{file_id}", response_model=StoredFileRead)
def get_file(
    file_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_storage_admin(principal)
    return storage_service.get_file(db, file_id)


__all__ = ["file_router", "router"]
