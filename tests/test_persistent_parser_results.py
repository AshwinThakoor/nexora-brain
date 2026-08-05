from __future__ import annotations

import json
from pathlib import Path

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
from nexora_knowledge.models import (
    DocumentType,
    ParseArtifactType,
    ParseResultStatus,
    SourceLicense,
    SourceType,
)
from nexora_knowledge.services import (
    document_service,
    ingestion_service,
    parse_result_service,
    parser_pipeline_service,
    source_service,
    storage_service,
)
from nexora_knowledge.services.exceptions import ResourceValidationError
from nexora_knowledge.storage import LocalStorageProvider, NullStorageProvider


def _enable_foreign_keys(engine) -> None:
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def parse_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def _settings(*, provider_type: str = "null", root: str = ".") -> Settings:
    return Settings(
        max_upload_size=1024 * 1024,
        allowed_extensions="txt,md,markdown,html,htm,docx,pdf",
        allowed_mime_types=(
            "text/plain,text/markdown,text/x-markdown,text/html,"
            "application/xhtml+xml,application/pdf,"
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        default_storage_provider=provider_type,
        local_storage_root=root,
    )


def _stored_file(
    db: Session,
    provider,
    *,
    suffix: str,
    content: bytes,
    filename: str = "fixture.txt",
    mime_type: str = "text/plain",
):
    license_record = SourceLicense(
        name=f"Parse Licence {suffix}",
        slug=f"parse-licence-{suffix}",
        allows_ingestion=True,
        allows_distribution=False,
    )
    db.add(license_record)
    db.commit()
    source = source_service.create_source(
        db,
        {
            "slug": f"parse-source-{suffix}",
            "title": f"Parse Source {suffix}",
            "source_type": SourceType.RESEARCH_PAPER,
            "language": "en",
            "trust_level": "official",
            "license_id": license_record.id,
        },
    )
    document = document_service.register_document(
        db,
        {
            "slug": f"parse-document-{suffix}",
            "source_id": source.id,
            "title": f"Parse Document {suffix}",
            "document_type": DocumentType.RESEARCH,
            "language": "en",
        },
    )
    version = document_service.register_version(
        db,
        document.id,
        {
            "version": "1.0",
            "checksum": f"parse-checksum-{suffix}",
        },
    )
    settings = _settings(
        provider_type=provider.provider_type.value,
        root=str(getattr(provider, "root", ".")),
    )
    upload = storage_service.create_upload_session(
        db,
        f"admin-{suffix}",
        settings=settings,
    )
    stored = storage_service.store_file(
        db,
        upload.id,
        version.id,
        filename,
        mime_type,
        content,
        provider=provider,
        settings=settings,
    )
    storage_service.complete_upload(db, upload.id)
    return stored, document, settings


def _reserved_job(db: Session, document_id: int, *, suffix: str):
    node = ingestion_service.register_processing_node(
        db,
        {
            "node_name": f"parse-node-{suffix}",
            "node_version": "1.0.0",
            "hostname": f"{suffix}.internal",
        },
    )
    job = ingestion_service.create_job(
        db,
        {"document_id": document_id, "priority": 25},
    )
    ingestion_service.queue_job(db, job.id)
    return ingestion_service.reserve_job(db, job.id, node.id)


def test_parse_result_lifecycle_is_deterministic_idempotent_and_immutable(
    parse_db: Session,
) -> None:
    provider = NullStorageProvider()
    stored, document, settings = _stored_file(
        parse_db,
        provider,
        suffix="lifecycle",
        content=b"# TITLE\n\nPersistent parser output.",
    )
    first_job = _reserved_job(
        parse_db,
        document.id,
        suffix="lifecycle-one",
    )
    first = parser_pipeline_service.parse_stored_file(
        parse_db,
        stored.id,
        ingestion_job_id=first_job.id,
        provider=provider,
        settings=settings,
    )

    assert first.status == ParseResultStatus.SUCCEEDED.value
    assert first.input_sha256 == stored.sha256
    assert first.content_hash == parse_result_service.calculate_content_hash(
        first.canonical_json
    )
    assert first.canonical_json == json.dumps(
        json.loads(first.canonical_json),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert [item.attempt_number for item in first.executions] == [1]
    assert {item.artifact_type for item in first.artifacts} >= {
        "canonical_manifest",
        "metadata",
        "statistics",
    }
    assert ingestion_service.get_job(parse_db, first_job.id).status == (
        "succeeded"
    )

    second_job = _reserved_job(
        parse_db,
        document.id,
        suffix="lifecycle-two",
    )
    repeated = parser_pipeline_service.parse_stored_file(
        parse_db,
        stored.id,
        ingestion_job_id=second_job.id,
        provider=provider,
        settings=settings,
    )
    assert repeated.id == first.id
    assert len(repeated.executions) == 1

    third_job = _reserved_job(
        parse_db,
        document.id,
        suffix="lifecycle-three",
    )
    reparsed = parser_pipeline_service.reparse_stored_file(
        parse_db,
        stored.id,
        ingestion_job_id=third_job.id,
        provider=provider,
        settings=settings,
    )
    assert reparsed.id == first.id
    assert [item.attempt_number for item in reparsed.executions] == [1, 2]
    assert all(item.status == "succeeded" for item in reparsed.executions)

    other_version = parse_result_service.create_or_get_parse_result(
        parse_db,
        stored.id,
        "txt",
        "99.0.0",
    )
    assert other_version.id != first.id

    first.canonical_json = "{}"
    with pytest.raises(ValueError, match="immutable"):
        parse_db.commit()
    parse_db.rollback()

    invalidated = parse_result_service.invalidate_parse_result(
        parse_db,
        first.id,
    )
    assert invalidated.status == "invalidated"
    assert parse_result_service.get_current_parse_result(
        parse_db,
        stored.id,
    ) is None


def test_failed_parse_preserves_safe_attempt_history(
    parse_db: Session,
) -> None:
    provider = NullStorageProvider()
    stored, document, settings = _stored_file(
        parse_db,
        provider,
        suffix="failure",
        content=b"\xff\xfe\xff",
        filename="failure.md",
        mime_type="text/markdown",
    )
    job = _reserved_job(parse_db, document.id, suffix="failure")

    with pytest.raises(ResourceValidationError, match="UTF-8"):
        parser_pipeline_service.parse_stored_file(
            parse_db,
            stored.id,
            ingestion_job_id=job.id,
            provider=provider,
            settings=settings,
        )

    results, total = parse_result_service.list_parse_results(
        parse_db,
        stored_file_id=stored.id,
    )
    assert total == 1
    failed = results[0]
    assert failed.status == "failed"
    assert failed.canonical_json is None
    history = parse_result_service.get_parse_history(parse_db, failed.id)
    assert len(history) == 1
    assert history[0].status == "failed"
    assert history[0].error_code == "INVALIDPARSERINPUTERROR"
    assert "Traceback" not in history[0].error_message
    assert ingestion_service.get_job(parse_db, job.id).status == "failed"


@pytest.mark.parametrize("missing", [False, True])
def test_pipeline_detects_integrity_and_missing_object_failures(
    parse_db: Session,
    missing: bool,
) -> None:
    provider = NullStorageProvider()
    stored, document, settings = _stored_file(
        parse_db,
        provider,
        suffix=f"integrity-{missing}",
        content=b"integrity bytes",
    )
    if missing:
        provider.delete(stored.storage_path)
    else:
        provider.objects[stored.storage_path] = b"tampered-bytes!"
    job = _reserved_job(
        parse_db,
        document.id,
        suffix=f"integrity-{missing}",
    )

    with pytest.raises(ResourceValidationError):
        parser_pipeline_service.parse_stored_file(
            parse_db,
            stored.id,
            ingestion_job_id=job.id,
            provider=provider,
            settings=settings,
        )
    assert ingestion_service.get_job(parse_db, job.id).status == "failed"


def test_local_storage_provider_supports_pipeline_reads(
    parse_db: Session,
    tmp_path: Path,
) -> None:
    provider = LocalStorageProvider(tmp_path / "objects")
    stored, document, settings = _stored_file(
        parse_db,
        provider,
        suffix="local",
        content=b"LOCAL\n\nLocal provider paragraph.",
    )
    job = _reserved_job(parse_db, document.id, suffix="local")
    result = parser_pipeline_service.parse_stored_file(
        parse_db,
        stored.id,
        ingestion_job_id=job.id,
        provider=provider,
        settings=settings,
    )
    assert result.status == "succeeded"


def test_artifact_creation_filtering_and_history_ordering(
    parse_db: Session,
) -> None:
    provider = NullStorageProvider()
    stored, document, settings = _stored_file(
        parse_db,
        provider,
        suffix="queries",
        content=b"QUERY\n\nSearchable output.",
    )
    job = _reserved_job(parse_db, document.id, suffix="queries")
    result = parser_pipeline_service.parse_stored_file(
        parse_db,
        stored.id,
        ingestion_job_id=job.id,
        provider=provider,
        settings=settings,
    )
    artifact = parse_result_service.add_parse_artifact(
        parse_db,
        result.id,
        ParseArtifactType.VALIDATION_REPORT,
        "validation",
        content_json={"valid": True},
    )
    assert len(artifact.checksum) == 64
    items, total = parse_result_service.list_parse_results(
        parse_db,
        stored_file_id=stored.id,
        parser_name="txt",
        parser_version="1.0.0",
        status="succeeded",
        input_sha256=stored.sha256,
        content_hash=result.content_hash,
        sort_by="created_at",
        sort_order="asc",
        limit=1,
    )
    assert total == 1
    assert items[0].id == result.id
    assert [item.attempt_number for item in result.executions] == [1]


@pytest.fixture
def parse_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    provider = NullStorageProvider()
    with factory() as db:
        stored, document, settings = _stored_file(
            db,
            provider,
            suffix="api",
            content=b"API\n\nPersistent API output.",
        )
        job = _reserved_job(db, document.id, suffix="api")
        file_id = stored.id
        job_id = job.id

    def override_get_db():
        with factory() as db:
            yield db

    monkeypatch.setattr(api_package, "init_database", lambda: None)
    monkeypatch.setattr(
        parser_pipeline_service,
        "get_default_storage_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        parser_pipeline_service,
        "get_settings",
        lambda: settings,
    )
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, file_id, job_id
    app.dependency_overrides.clear()
    engine.dispose()


def _headers(role: str) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": f"{role}-parse-result-test",
        "X-Nexora-Principal-Role": role,
    }


def test_parse_result_api_authorization_and_safe_views(parse_client) -> None:
    client, file_id, job_id = parse_client
    for role in ("learner", "instructor", "reviewer"):
        response = client.post(
            f"/api/v1/files/{file_id}/parse",
            json={"ingestion_job_id": job_id},
            headers=_headers(role),
        )
        assert response.status_code == 403

    parsed = client.post(
        f"/api/v1/files/{file_id}/parse",
        json={"ingestion_job_id": job_id},
        headers=_headers("admin"),
    )
    assert parsed.status_code == 200, parsed.text
    payload = parsed.json()
    result_id = payload["id"]
    assert payload["canonical_json"]["parser_name"] == "txt"
    assert "storage_path" not in parsed.text

    assert client.get(
        f"/api/v1/files/{file_id}/parse-results",
        headers=_headers("learner"),
    ).status_code == 403
    instructor_list = client.get(
        f"/api/v1/files/{file_id}/parse-results",
        params={"status": "succeeded", "limit": 1},
        headers=_headers("instructor"),
    )
    assert instructor_list.status_code == 200
    assert instructor_list.json()["total"] == 1
    instructor_read = client.get(
        f"/api/v1/parse-results/{result_id}",
        headers=_headers("instructor"),
    )
    assert instructor_read.status_code == 200
    assert instructor_read.json()["canonical_json"] is None
    assert instructor_read.json()["executions"] == []

    history = client.get(
        f"/api/v1/parse-results/{result_id}/history",
        headers=_headers("reviewer"),
    )
    assert history.status_code == 200
    assert history.json()["executions"][0]["status"] == "succeeded"
    assert client.get(
        f"/api/v1/parse-results/{result_id}/history",
        headers=_headers("instructor"),
    ).status_code == 403
    assert client.get(
        f"/api/v1/parse-results/{result_id}/artifacts",
        headers=_headers("reviewer"),
    ).status_code == 403
    artifacts = client.get(
        f"/api/v1/parse-results/{result_id}/artifacts",
        headers=_headers("admin"),
    )
    assert artifacts.status_code == 200
    assert artifacts.json()
    assert "storage_path" not in artifacts.text
