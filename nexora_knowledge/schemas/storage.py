from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .common import ORMResponse


class UploadSessionCreate(ORMResponse):
    ttl_seconds: int | None = Field(default=None, ge=60, le=86400)


class FileHashRead(ORMResponse):
    id: int
    stored_file_id: int
    algorithm: str
    value: str


class StoredFileRead(ORMResponse):
    id: int
    uuid: str
    upload_session_id: int
    document_version_id: int
    original_filename: str
    normalized_filename: str
    storage_provider: str
    storage_path: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    sha1: str | None
    md5: str | None
    created_at: datetime
    hashes: list[FileHashRead]


class UploadSessionRead(ORMResponse):
    id: int
    uuid: str
    status: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    stored_file: StoredFileRead | None


class StorageProviderRead(ORMResponse):
    id: int
    name: str
    provider_type: str
    active: bool
    created_at: datetime


__all__ = [
    "FileHashRead",
    "StorageProviderRead",
    "StoredFileRead",
    "UploadSessionCreate",
    "UploadSessionRead",
]
