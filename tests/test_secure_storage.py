from __future__ import annotations

from datetime import timedelta
import hashlib
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import nexora_knowledge.api as api_package
from nexora_knowledge.api import app
from nexora_knowledge.api.dependencies import get_db
from nexora_knowledge.config import Settings
from nexora_knowledge.database import Base
from nexora_knowledge.models import DocumentType, SourceLicense, SourceType
from nexora_knowledge.services import (
    document_service,
    source_service,
    storage_service,
)
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceValidationError,
)
from nexora_knowledge.storage import LocalStorageProvider, NullStorageProvider


def _enable_foreign_keys(engine) -> None:
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def storage_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def storage_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        version_id = _document_version(session)
    provider = NullStorageProvider()

    def override_get_db():
        with session_factory() as session:
            yield session

    monkeypatch.setattr(api_package, "init_database", lambda: None)
    monkeypatch.setattr(
        storage_service,
        "get_default_storage_provider",
        lambda: provider,
    )
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, version_id, provider
    app.dependency_overrides.clear()
    engine.dispose()


def _headers(role: str) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": f"{role}-storage-test",
        "X-Nexora-Principal-Role": role,
    }


def _settings(*, maximum_size: int = 1024) -> Settings:
    return Settings(
        max_upload_size=maximum_size,
        allowed_extensions="txt,pdf",
        allowed_mime_types="text/plain,application/pdf",
        default_storage_provider="null",
        upload_session_ttl_seconds=3600,
    )


def _document_version(db: Session, *, suffix: str = "one") -> int:
    license_record = SourceLicense(
        name=f"Storage Licence {suffix}",
        slug=f"storage-licence-{suffix}",
        allows_ingestion=True,
        allows_distribution=False,
    )
    db.add(license_record)
    db.commit()
    source = source_service.create_source(
        db,
        {
            "slug": f"storage-source-{suffix}",
            "title": f"Storage Source {suffix}",
            "source_type": SourceType.RESEARCH_PAPER,
            "language": "en",
            "trust_level": "official",
            "license_id": license_record.id,
        },
    )
    document = document_service.register_document(
        db,
        {
            "slug": f"storage-document-{suffix}",
            "source_id": source.id,
            "title": f"Storage Document {suffix}",
            "document_type": DocumentType.RESEARCH,
            "language": "en",
        },
    )
    version = document_service.register_version(
        db,
        document.id,
        {
            "version": "1.0",
            "checksum": f"storage-checksum-{suffix}",
        },
    )
    return version.id


def test_filename_normalization_and_hashing() -> None:
    assert storage_service.normalize_filename(
        r"C:\fakepath\Quarterly Report (Final).PDF"
    ) == "Quarterly_Report_Final.pdf"
    assert storage_service.normalize_filename("../../CON.txt") == "file_CON.txt"
    hashes = storage_service.compute_hashes(b"hello")
    assert hashes["sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert hashes["sha1"] == hashlib.sha1(b"hello").hexdigest()
    assert len(hashes["md5"]) == 32


def test_upload_session_store_complete_and_document_link(
    storage_db: Session,
) -> None:
    version_id = _document_version(storage_db)
    provider = NullStorageProvider()
    upload = storage_service.create_upload_session(
        storage_db,
        "admin-storage",
        settings=_settings(),
    )
    assert upload.status == "created"
    stored = storage_service.store_file(
        storage_db,
        upload.id,
        version_id,
        "Research Notes.txt",
        "text/plain; charset=utf-8",
        b"secure upload content",
        provider=provider,
        settings=_settings(),
    )
    assert stored.storage_provider == "null"
    assert stored.normalized_filename == "Research_Notes.txt"
    assert provider.exists(stored.storage_path)
    assert {item.algorithm for item in stored.hashes} == {
        "sha256",
        "sha1",
        "md5",
    }

    completed = storage_service.complete_upload(storage_db, upload.id)
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert completed.stored_file.id == stored.id
    loaded_version = storage_db.get(
        type(stored.document_version),
        version_id,
    )
    assert [item.id for item in loaded_version.stored_files] == [stored.id]
    assert document_service.validate_ingestion_eligibility(
        storage_db,
        completed.stored_file.document_version.document_id,
    )

    other_version_id = _document_version(storage_db, suffix="two")
    linked = storage_service.link_file_to_document_version(
        storage_db,
        stored.id,
        other_version_id,
    )
    assert linked.document_version_id == other_version_id


def test_duplicate_sha256_is_rejected_and_session_fails(
    storage_db: Session,
) -> None:
    version_id = _document_version(storage_db)
    provider = NullStorageProvider()
    first_session = storage_service.create_upload_session(
        storage_db,
        "admin-storage",
        settings=_settings(),
    )
    storage_service.store_file(
        storage_db,
        first_session.id,
        version_id,
        "first.txt",
        "text/plain",
        b"duplicate bytes",
        provider=provider,
        settings=_settings(),
    )
    storage_service.complete_upload(storage_db, first_session.id)

    second_session = storage_service.create_upload_session(
        storage_db,
        "admin-storage",
        settings=_settings(),
    )
    with pytest.raises(ResourceConflictError, match="SHA-256"):
        storage_service.store_file(
            storage_db,
            second_session.id,
            version_id,
            "second.txt",
            "text/plain",
            b"duplicate bytes",
            provider=provider,
            settings=_settings(),
        )
    assert storage_service.get_upload_session(
        storage_db,
        second_session.id,
    ).status == "failed"


@pytest.mark.parametrize(
    ("filename", "mime_type", "content", "maximum_size", "message"),
    [
        ("empty.txt", "text/plain", b"", 100, "Zero-byte"),
        ("large.txt", "text/plain", b"12345", 4, "maximum file size"),
        ("malware.exe", "text/plain", b"x", 100, "extension"),
        (
            "notes.txt",
            "application/octet-stream",
            b"x",
            100,
            "MIME type",
        ),
        (
            "notes.pdf",
            "text/plain",
            b"x",
            100,
            "does not match",
        ),
    ],
)
def test_upload_validation_rejections(
    storage_db: Session,
    filename: str,
    mime_type: str,
    content: bytes,
    maximum_size: int,
    message: str,
) -> None:
    version_id = _document_version(storage_db)
    upload = storage_service.create_upload_session(
        storage_db,
        "admin-storage",
        settings=_settings(maximum_size=maximum_size),
    )
    with pytest.raises(ResourceValidationError, match=message):
        storage_service.store_file(
            storage_db,
            upload.id,
            version_id,
            filename,
            mime_type,
            content,
            provider=NullStorageProvider(),
            settings=_settings(maximum_size=maximum_size),
        )
    assert storage_service.get_upload_session(
        storage_db,
        upload.id,
    ).status == "failed"


def test_cancellation_and_expiration_remove_partial_storage(
    storage_db: Session,
) -> None:
    version_id = _document_version(storage_db)
    provider = NullStorageProvider()
    upload = storage_service.create_upload_session(
        storage_db,
        "admin-storage",
        settings=_settings(),
    )
    stored = storage_service.store_file(
        storage_db,
        upload.id,
        version_id,
        "cancel.txt",
        "text/plain",
        b"cancel this",
        provider=provider,
        settings=_settings(),
    )
    assert provider.exists(stored.storage_path)
    cancelled = storage_service.cancel_upload(
        storage_db,
        upload.id,
        provider=provider,
    )
    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None
    assert cancelled.stored_file is None
    assert not provider.exists(stored.storage_path)

    expiring = storage_service.create_upload_session(
        storage_db,
        "admin-storage",
        ttl_seconds=60,
        settings=_settings(),
    )
    expired = storage_service.expire_upload(
        storage_db,
        expiring.id,
        as_of=expiring.expires_at + timedelta(seconds=1),
    )
    assert expired.status == "expired"


def test_local_storage_provider_enforces_root_and_writes_atomically(
    tmp_path,
) -> None:
    provider = LocalStorageProvider(tmp_path / "uploads")
    size = provider.store(
        BytesIO(b"local bytes"),
        "ab/cd/object.txt",
    )
    assert size == len(b"local bytes")
    assert provider.exists("ab/cd/object.txt")
    with pytest.raises(ValueError, match="safe relative"):
        provider.store(
            BytesIO(b"escape"),
            "../escape.txt",
        )
    provider.delete("ab/cd/object.txt")
    assert not provider.exists("ab/cd/object.txt")


def test_storage_api_is_admin_only_and_accepts_multipart(
    storage_client,
) -> None:
    client, version_id, provider = storage_client
    assert client.post("/api/v1/uploads/session").status_code == 401
    for role in ("learner", "instructor", "reviewer"):
        assert client.post(
            "/api/v1/uploads/session",
            headers=_headers(role),
        ).status_code == 403

    session_response = client.post(
        "/api/v1/uploads/session",
        json={"ttl_seconds": 600},
        headers=_headers("admin"),
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]
    uploaded = client.post(
        f"/api/v1/uploads/{session_id}",
        data={"document_version_id": str(version_id)},
        files={
            "file": (
                "API Upload.txt",
                b"multipart upload",
                "text/plain",
            )
        },
        headers=_headers("admin"),
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["status"] == "completed"
    file_id = body["stored_file"]["id"]
    assert provider.exists(body["stored_file"]["storage_path"])

    assert client.get(
        f"/api/v1/files/{file_id}",
        headers=_headers("reviewer"),
    ).status_code == 403
    file_response = client.get(
        f"/api/v1/files/{file_id}",
        headers=_headers("admin"),
    )
    assert file_response.status_code == 200
    assert file_response.json()["normalized_filename"] == "API_Upload.txt"
    assert client.get(
        f"/api/v1/uploads/{session_id}",
        headers=_headers("admin"),
    ).json()["status"] == "completed"

    cancellable = client.post(
        "/api/v1/uploads/session",
        headers=_headers("admin"),
    )
    assert client.delete(
        f"/api/v1/uploads/{cancellable.json()['id']}",
        headers=_headers("admin"),
    ).status_code == 204
