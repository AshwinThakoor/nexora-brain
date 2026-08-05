from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
from pathlib import PurePosixPath
import re
from tempfile import SpooledTemporaryFile
from typing import BinaryIO
import unicodedata
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..config import Settings, get_settings
from ..models import (
    DocumentVersion,
    FileHash,
    HashAlgorithm,
    StorageProvider,
    StorageProviderType,
    StoredFile,
    UploadSession,
    UploadStatus,
)
from ..models.common import utc_now
from ..storage import AbstractStorageProvider, get_default_storage_provider
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


_TERMINAL_UPLOAD_STATUSES = frozenset(
    {
        UploadStatus.COMPLETED.value,
        UploadStatus.CANCELLED.value,
        UploadStatus.EXPIRED.value,
    }
)
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)
_MIME_BY_EXTENSION = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    },
    "txt": {"text/plain"},
    "csv": {"text/csv", "text/plain"},
    "md": {"text/markdown", "text/plain"},
    "markdown": {"text/markdown", "text/plain", "text/x-markdown"},
    "html": {"text/html", "application/xhtml+xml"},
    "htm": {"text/html", "application/xhtml+xml"},
    "json": {"application/json", "text/json"},
}


def _session_query():
    return (
        select(UploadSession)
        .options(
            selectinload(UploadSession.stored_file).selectinload(
                StoredFile.hashes
            )
        )
        .execution_options(populate_existing=True)
    )


def _file_query():
    return (
        select(StoredFile)
        .options(
            selectinload(StoredFile.hashes),
            selectinload(StoredFile.upload_session),
            selectinload(StoredFile.document_version),
        )
        .execution_options(populate_existing=True)
    )


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def _matching_timezone(value: datetime, reference: datetime) -> datetime:
    if reference.tzinfo is None and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if reference.tzinfo is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _configured_values(raw: str, *, strip_dot: bool = False) -> frozenset[str]:
    values = []
    for item in raw.split(","):
        normalized = item.strip().casefold()
        if strip_dot:
            normalized = normalized.lstrip(".")
        if normalized:
            values.append(normalized)
    return frozenset(values)


def normalize_filename(filename: str) -> str:
    if not isinstance(filename, str):
        raise ResourceValidationError("Upload filename is required")
    if len(filename) > 1024:
        raise ResourceValidationError(
            "Upload filename cannot exceed 1024 characters"
        )
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename or basename in {".", ".."}:
        raise ResourceValidationError("Upload filename is invalid")
    ascii_name = (
        unicodedata.normalize("NFKD", basename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = "".join(
        character
        for character in ascii_name
        if ord(character) >= 32 and character != "\x7f"
    )
    ascii_name = re.sub(r"\s+", "_", ascii_name)
    ascii_name = re.sub(r"[^A-Za-z0-9._+-]", "", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip(" ._-")
    if not ascii_name:
        raise ResourceValidationError("Upload filename has no safe characters")

    path = PurePosixPath(ascii_name)
    extension = path.suffix.casefold()
    stem = path.stem.strip(" ._-") or "file"
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = f"file_{stem}"
    maximum_stem_length = max(1, 255 - len(extension))
    normalized = f"{stem[:maximum_stem_length]}{extension}"
    if normalized in {".", ".."} or len(normalized) > 255:
        raise ResourceValidationError("Upload filename could not be normalized")
    return normalized


def validate_upload(
    filename: str,
    mime_type: str,
    size_bytes: int,
    *,
    settings: Settings | None = None,
) -> dict[str, str | int]:
    resolved_settings = settings or get_settings()
    normalized_filename = normalize_filename(filename)
    extension = PurePosixPath(normalized_filename).suffix.casefold().lstrip(".")
    normalized_mime = mime_type.split(";", 1)[0].strip().casefold()
    if size_bytes <= 0:
        raise ResourceValidationError("Zero-byte uploads are not allowed")
    if size_bytes > resolved_settings.max_upload_size:
        raise ResourceValidationError(
            "Upload exceeds the configured maximum file size"
        )
    allowed_extensions = _configured_values(
        resolved_settings.allowed_extensions,
        strip_dot=True,
    )
    if extension not in allowed_extensions:
        raise ResourceValidationError(
            f"Upload extension '.{extension}' is not allowed"
        )
    allowed_mime_types = _configured_values(
        resolved_settings.allowed_mime_types
    )
    if normalized_mime not in allowed_mime_types:
        raise ResourceValidationError(
            f"Upload MIME type '{normalized_mime}' is not allowed"
        )
    compatible_mimes = _MIME_BY_EXTENSION.get(extension)
    if compatible_mimes is not None and normalized_mime not in compatible_mimes:
        raise ResourceValidationError(
            "Upload MIME type does not match its filename extension"
        )
    return {
        "normalized_filename": normalized_filename,
        "extension": extension,
        "mime_type": normalized_mime,
        "size_bytes": size_bytes,
    }


def _hashers() -> dict[str, object]:
    try:
        md5_hasher = hashlib.md5(usedforsecurity=False)
    except TypeError:
        md5_hasher = hashlib.md5()
    return {
        HashAlgorithm.SHA256.value: hashlib.sha256(),
        HashAlgorithm.SHA1.value: hashlib.sha1(),
        HashAlgorithm.MD5.value: md5_hasher,
    }


def _as_stream(content: bytes | bytearray | BinaryIO) -> BinaryIO:
    if isinstance(content, (bytes, bytearray)):
        return BytesIO(bytes(content))
    if not hasattr(content, "read"):
        raise ResourceValidationError("Upload content must be a binary stream")
    return content


def compute_hashes(
    content: bytes | bytearray | BinaryIO,
) -> dict[str, str]:
    stream = _as_stream(content)
    original_position = None
    if hasattr(stream, "tell") and hasattr(stream, "seek"):
        try:
            original_position = stream.tell()
        except (OSError, ValueError):
            original_position = None
    hashers = _hashers()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        for hasher in hashers.values():
            hasher.update(chunk)
    if original_position is not None:
        stream.seek(original_position)
    return {
        algorithm: hasher.hexdigest()
        for algorithm, hasher in hashers.items()
    }


def _spool_and_hash(
    content: bytes | bytearray | BinaryIO,
    *,
    maximum_size: int,
) -> tuple[SpooledTemporaryFile, int, dict[str, str]]:
    source = _as_stream(content)
    spool = SpooledTemporaryFile(max_size=min(maximum_size, 8 * 1024 * 1024))
    hashers = _hashers()
    size = 0
    try:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > maximum_size:
                raise ResourceValidationError(
                    "Upload exceeds the configured maximum file size"
                )
            spool.write(chunk)
            for hasher in hashers.values():
                hasher.update(chunk)
        spool.seek(0)
        hashes = {
            algorithm: hasher.hexdigest()
            for algorithm, hasher in hashers.items()
        }
        return spool, size, hashes
    except Exception:
        spool.close()
        raise


def create_upload_session(
    db: Session,
    created_by: str | Mapping[str, object],
    *,
    ttl_seconds: int | None = None,
    settings: Settings | None = None,
) -> UploadSession:
    resolved_settings = settings or get_settings()
    if isinstance(created_by, Mapping):
        values = created_by
        creator = str(values.get("created_by", "")).strip()
        if ttl_seconds is None and values.get("ttl_seconds") is not None:
            try:
                ttl_seconds = int(values["ttl_seconds"])
            except (TypeError, ValueError) as exc:
                raise ResourceValidationError(
                    "Upload session TTL must be an integer"
                ) from exc
    else:
        creator = created_by.strip()
    if not creator or len(creator) > 255:
        raise ResourceValidationError(
            "Upload session creator must contain between 1 and 255 characters"
        )
    ttl = (
        resolved_settings.upload_session_ttl_seconds
        if ttl_seconds is None
        else ttl_seconds
    )
    if not 60 <= ttl <= 86400:
        raise ResourceValidationError(
            "Upload session TTL must be between 60 and 86400 seconds"
        )
    created_at = utc_now()
    session = UploadSession(
        status=UploadStatus.CREATED.value,
        created_by=creator,
        created_at=created_at,
        expires_at=created_at + timedelta(seconds=ttl),
    )
    db.add(session)
    _commit(db, "Upload session could not be created")
    return get_upload_session(db, session.id)


def get_upload_session(db: Session, session_id: int) -> UploadSession:
    session = db.scalar(
        _session_query().where(UploadSession.id == session_id)
    )
    if session is None:
        raise ResourceNotFoundError("Upload session", session_id)
    return session


def _locked_session(db: Session, session_id: int) -> UploadSession:
    session = db.scalar(
        select(UploadSession)
        .where(UploadSession.id == session_id)
        .with_for_update()
    )
    if session is None:
        raise ResourceNotFoundError("Upload session", session_id)
    return session


def _is_expired(session: UploadSession, now: datetime | None = None) -> bool:
    current = _matching_timezone(now or utc_now(), session.expires_at)
    return session.expires_at <= current


def _mark_failed(db: Session, session_id: int) -> None:
    db.rollback()
    session = db.get(UploadSession, session_id)
    if session is not None and session.status not in _TERMINAL_UPLOAD_STATUSES:
        session.status = UploadStatus.FAILED.value
        db.commit()


def _provider_for_file(
    stored_file: StoredFile,
    provider: AbstractStorageProvider | None,
) -> AbstractStorageProvider:
    resolved = provider or get_default_storage_provider()
    if resolved.provider_type.value != stored_file.storage_provider:
        raise ResourceValidationError(
            "Configured storage provider does not own this file"
        )
    return resolved


def _ensure_provider_inventory(
    db: Session,
    provider: AbstractStorageProvider,
) -> None:
    provider_type = provider.provider_type.value
    record = db.scalar(
        select(StorageProvider).where(
            StorageProvider.provider_type == provider_type
        )
    )
    if record is None:
        db.add(
            StorageProvider(
                name=provider_type,
                provider_type=provider_type,
                active=True,
            )
        )
    elif not record.active:
        raise ResourceValidationError(
            f"Storage provider '{provider_type}' is inactive"
        )


def store_file(
    db: Session,
    session_id: int,
    document_version_id: int,
    original_filename: str,
    mime_type: str,
    content: bytes | bytearray | BinaryIO,
    *,
    provider: AbstractStorageProvider | None = None,
    settings: Settings | None = None,
) -> StoredFile:
    resolved_settings = settings or get_settings()
    resolved_provider = provider or get_default_storage_provider()
    upload_session = _locked_session(db, session_id)
    if _is_expired(upload_session):
        db.rollback()
        expire_upload(
            db,
            session_id,
            provider=resolved_provider,
            as_of=utc_now(),
        )
        raise ResourceValidationError("Upload session has expired")
    if upload_session.status != UploadStatus.CREATED.value:
        raise ResourceValidationError(
            "Only a newly created upload session can receive a file"
        )
    if db.get(DocumentVersion, document_version_id) is None:
        raise ResourceNotFoundError("Document version", document_version_id)

    upload_session.status = UploadStatus.RECEIVING.value
    db.flush()
    spool = None
    storage_path = None
    try:
        spool, size, hashes = _spool_and_hash(
            content,
            maximum_size=resolved_settings.max_upload_size,
        )
        validation = validate_upload(
            original_filename,
            mime_type,
            size,
            settings=resolved_settings,
        )
        upload_session.status = UploadStatus.VALIDATING.value
        duplicate = db.scalar(
            select(StoredFile.id).where(
                func.lower(StoredFile.sha256)
                == hashes[HashAlgorithm.SHA256.value]
            )
        )
        if duplicate is not None:
            raise ResourceConflictError(
                "A file with this SHA-256 hash already exists"
            )
        _ensure_provider_inventory(db, resolved_provider)
        file_uuid = str(uuid4())
        suffix = (
            f".{validation['extension']}"
            if validation["extension"]
            else ""
        )
        storage_path = (
            f"{file_uuid[:2]}/{file_uuid[2:4]}/{file_uuid}{suffix}"
        )
        written_size = resolved_provider.store(spool, storage_path)
        if written_size != size:
            raise ResourceValidationError(
                "Storage provider wrote an unexpected number of bytes"
            )
        record = StoredFile(
            uuid=file_uuid,
            upload_session_id=upload_session.id,
            document_version_id=document_version_id,
            original_filename=original_filename.strip(),
            normalized_filename=str(validation["normalized_filename"]),
            storage_provider=resolved_provider.provider_type.value,
            storage_path=storage_path,
            mime_type=str(validation["mime_type"]),
            extension=str(validation["extension"]),
            size_bytes=size,
            sha256=hashes[HashAlgorithm.SHA256.value],
            sha1=hashes[HashAlgorithm.SHA1.value],
            md5=hashes[HashAlgorithm.MD5.value],
        )
        db.add(record)
        db.flush()
        for algorithm, value in hashes.items():
            db.add(
                FileHash(
                    stored_file_id=record.id,
                    algorithm=algorithm,
                    value=value,
                )
            )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            resolved_provider.delete(storage_path)
            _mark_failed(db, session_id)
            raise ResourceConflictError(
                "A file with this SHA-256 hash already exists"
            ) from exc
        return get_file(db, record.id)
    except (ResourceConflictError, ResourceNotFoundError, ResourceValidationError):
        if storage_path and resolved_provider.exists(storage_path):
            resolved_provider.delete(storage_path)
        _mark_failed(db, session_id)
        raise
    except Exception as exc:
        if storage_path and resolved_provider.exists(storage_path):
            resolved_provider.delete(storage_path)
        _mark_failed(db, session_id)
        raise ResourceValidationError(
            "File could not be stored safely"
        ) from exc
    finally:
        if spool is not None:
            spool.close()


def complete_upload(db: Session, session_id: int) -> UploadSession:
    session = _locked_session(db, session_id)
    if session.status != UploadStatus.VALIDATING.value:
        raise ResourceValidationError(
            "Only a validated upload can be completed"
        )
    stored_file_id = db.scalar(
        select(StoredFile.id).where(
            StoredFile.upload_session_id == session.id
        )
    )
    if stored_file_id is None:
        raise ResourceValidationError(
            "Upload session has no validated stored file"
        )
    session.status = UploadStatus.COMPLETED.value
    session.completed_at = utc_now()
    _commit(db, "Upload session could not be completed")
    return get_upload_session(db, session.id)


def _remove_stored_file(
    db: Session,
    stored_file: StoredFile,
    provider: AbstractStorageProvider | None,
) -> None:
    resolved_provider = _provider_for_file(stored_file, provider)
    resolved_provider.delete(stored_file.storage_path)
    db.delete(stored_file)


def cancel_upload(
    db: Session,
    session_id: int,
    *,
    provider: AbstractStorageProvider | None = None,
) -> UploadSession:
    session = _locked_session(db, session_id)
    if session.status in {
        UploadStatus.COMPLETED.value,
        UploadStatus.CANCELLED.value,
        UploadStatus.EXPIRED.value,
    }:
        raise ResourceValidationError(
            f"Upload session in '{session.status}' state cannot be cancelled"
        )
    stored_file = db.scalar(
        select(StoredFile).where(
            StoredFile.upload_session_id == session.id
        )
    )
    if stored_file is not None:
        _remove_stored_file(db, stored_file, provider)
    session.status = UploadStatus.CANCELLED.value
    session.cancelled_at = utc_now()
    session.completed_at = None
    _commit(db, "Upload session could not be cancelled")
    return get_upload_session(db, session.id)


def expire_upload(
    db: Session,
    session_id: int,
    *,
    provider: AbstractStorageProvider | None = None,
    as_of: datetime | None = None,
) -> UploadSession:
    session = _locked_session(db, session_id)
    now = as_of or utc_now()
    if session.status in _TERMINAL_UPLOAD_STATUSES:
        raise ResourceValidationError(
            f"Upload session in '{session.status}' state cannot expire"
        )
    if not _is_expired(session, now):
        raise ResourceValidationError("Upload session has not expired")
    stored_file = db.scalar(
        select(StoredFile).where(
            StoredFile.upload_session_id == session.id
        )
    )
    if stored_file is not None:
        _remove_stored_file(db, stored_file, provider)
    session.status = UploadStatus.EXPIRED.value
    session.completed_at = None
    _commit(db, "Upload session could not be expired")
    return get_upload_session(db, session.id)


def get_file(db: Session, file_id: int) -> StoredFile:
    stored_file = db.scalar(_file_query().where(StoredFile.id == file_id))
    if stored_file is None:
        raise ResourceNotFoundError("Stored file", file_id)
    return stored_file


def delete_file_metadata(
    db: Session,
    file_id: int,
    *,
    provider: AbstractStorageProvider | None = None,
) -> None:
    stored_file = get_file(db, file_id)
    upload_session = stored_file.upload_session
    _remove_stored_file(db, stored_file, provider)
    upload_session.status = UploadStatus.FAILED.value
    upload_session.completed_at = None
    _commit(db, "Stored file metadata could not be deleted")


def link_file_to_document_version(
    db: Session,
    file_id: int,
    document_version_id: int,
) -> StoredFile:
    stored_file = db.scalar(
        select(StoredFile)
        .where(StoredFile.id == file_id)
        .with_for_update()
    )
    if stored_file is None:
        raise ResourceNotFoundError("Stored file", file_id)
    if db.get(DocumentVersion, document_version_id) is None:
        raise ResourceNotFoundError("Document version", document_version_id)
    stored_file.document_version_id = document_version_id
    _commit(db, "Stored file could not be linked to the document version")
    return get_file(db, stored_file.id)


__all__ = [
    "cancel_upload",
    "complete_upload",
    "compute_hashes",
    "create_upload_session",
    "delete_file_metadata",
    "expire_upload",
    "get_file",
    "get_upload_session",
    "link_file_to_document_version",
    "normalize_filename",
    "store_file",
    "validate_upload",
]
