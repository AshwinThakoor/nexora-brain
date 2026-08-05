from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from ..config import get_settings
from ..models.canonical_document import CanonicalDocument
from ..schemas.parser import (
    ParserCapabilityRead,
    ParserValidationResponse,
)
from ..services import parser_service
from ..services.authorization import Principal, require_parser_admin
from ..services.exceptions import ResourceValidationError
from .dependencies import get_current_principal


router = APIRouter(
    prefix="/api/v1/parsers",
    tags=["document-parsers"],
)


@router.get("", response_model=list[ParserCapabilityRead])
def list_parsers(
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    return parser_service.get_supported_formats()


@router.post("/validate", response_model=ParserValidationResponse)
async def validate_parser_input(
    file: Annotated[UploadFile, File()],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    filename = file.filename or ""
    try:
        content = await _read_upload(file)
        parser = parser_service.select_parser(
            filename,
            mime_type=file.content_type,
        )
        parser_service.validate_document(
            content,
            filename=filename,
            mime_type=file.content_type,
        )
        return ParserValidationResponse(
            valid=True,
            filename=filename,
            parser_name=parser.parser_name(),
            parser_version=parser.parser_version(),
            implemented=parser.implemented,
        )
    finally:
        await file.close()


@router.post("/parse", response_model=CanonicalDocument)
async def parse_uploaded_document(
    file: Annotated[UploadFile, File()],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_parser_admin(principal)
    filename = file.filename or ""
    try:
        content = await _read_upload(file)
        return parser_service.parse_document(
            content,
            filename=filename,
            mime_type=file.content_type,
        )
    finally:
        await file.close()


async def _read_upload(file: UploadFile) -> bytes:
    maximum_size = get_settings().max_upload_size
    content = await file.read(maximum_size + 1)
    if len(content) > maximum_size:
        raise ResourceValidationError(
            f"Document exceeds maximum parser size of {maximum_size} bytes"
        )
    return content


__all__ = ["router"]
