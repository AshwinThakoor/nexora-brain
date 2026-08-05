from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import nexora_knowledge.api as api_package
from nexora_knowledge.api import app
from nexora_knowledge.api.dependencies import get_db
from nexora_knowledge.database import Base
from nexora_knowledge.models import (
    AuditEventType,
    DocumentType,
    JobStatus,
    SourceLicense,
    SourceType,
)
from nexora_knowledge.models.common import utc_now
from nexora_knowledge.services import (
    document_service,
    ingestion_service,
    source_service,
)
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceValidationError,
)


def _enable_foreign_keys(engine) -> None:
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def orchestration_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def orchestration_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        document_id = _eligible_document(session)

    def override_get_db():
        with session_factory() as session:
            yield session

    monkeypatch.setattr(api_package, "init_database", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, document_id
    app.dependency_overrides.clear()
    engine.dispose()


def _headers(role: str) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": f"{role}-ingestion-test",
        "X-Nexora-Principal-Role": role,
    }


def _eligible_document(
    db: Session,
    *,
    suffix: str = "primary",
) -> int:
    license_record = SourceLicense(
        name=f"Orchestration Licence {suffix}",
        slug=f"orchestration-licence-{suffix}",
        allows_ingestion=True,
        allows_distribution=False,
    )
    db.add(license_record)
    db.commit()
    source = source_service.create_source(
        db,
        {
            "slug": f"orchestration-source-{suffix}",
            "title": f"Orchestration Source {suffix}",
            "source_type": SourceType.RESEARCH_PAPER,
            "language": "en",
            "trust_level": "official",
            "license_id": license_record.id,
        },
    )
    document = document_service.register_document(
        db,
        {
            "slug": f"orchestration-document-{suffix}",
            "source_id": source.id,
            "title": f"Orchestration Document {suffix}",
            "document_type": DocumentType.RESEARCH,
            "language": "en",
            "publication_year": 2026,
        },
    )
    version = document_service.register_version(
        db,
        document.id,
        {
            "version": "1.0",
            "checksum": f"orchestration-checksum-{suffix}",
        },
    )
    document_service.register_file_metadata(
        db,
        version.id,
        {
            "original_filename": f"{suffix}.pdf",
            "storage_key": None,
            "mime_type": "application/pdf",
            "extension": "pdf",
            "size_bytes": 1024,
            "page_count": 5,
            "sha256": "a" * 63 + ("b" if suffix == "primary" else "c"),
            "processing_status": "ready",
        },
    )
    return document.id


def _node(db: Session, name: str = "node-a"):
    return ingestion_service.register_processing_node(
        db,
        {
            "node_name": name,
            "node_version": "1.0.0",
            "hostname": f"{name}.internal",
        },
    )


def _queued_job(db: Session, document_id: int):
    job = ingestion_service.create_job(
        db,
        {"document_id": document_id, "priority": 25},
    )
    return ingestion_service.queue_job(db, job.id)


def test_legal_state_transitions_attempt_and_audit_history(
    orchestration_db: Session,
) -> None:
    document_id = _eligible_document(orchestration_db)
    node = _node(orchestration_db)
    created = ingestion_service.create_job(
        orchestration_db,
        {"document_id": document_id, "priority": 10},
    )
    assert created.status == "new"

    queued = ingestion_service.queue_job(orchestration_db, created.id)
    reserved = ingestion_service.reserve_job(
        orchestration_db,
        queued.id,
        node.id,
        ttl_seconds=600,
    )
    assert reserved.status == "reserved"
    assert reserved.current_reservation.node_id == node.id

    running = ingestion_service.start_job(orchestration_db, reserved.id)
    assert running.status == "running"
    assert len(running.attempts) == 1
    assert running.attempts[0].status == "running"

    completed = ingestion_service.complete_job(
        orchestration_db,
        running.id,
    )
    assert completed.status == "succeeded"
    assert completed.completed_at is not None
    assert completed.attempts[0].status == "success"
    assert completed.attempts[0].finished_at is not None
    assert completed.attempts[0].duration_ms >= 0
    assert completed.current_reservation is None
    assert [
        item.event_type for item in completed.audit_events
    ] == [
        "created",
        "queued",
        "reserved",
        "started",
        "succeeded",
        "released",
    ]


def test_invalid_transitions_and_idempotent_job_creation(
    orchestration_db: Session,
) -> None:
    document_id = _eligible_document(orchestration_db)
    first = ingestion_service.create_job(
        orchestration_db,
        {"document_id": document_id},
    )
    duplicate = ingestion_service.create_job(
        orchestration_db,
        {"document_id": document_id, "priority": 999},
    )
    assert duplicate.id == first.id
    assert duplicate.priority == first.priority

    with pytest.raises(ResourceValidationError, match="Invalid"):
        ingestion_service.start_job(orchestration_db, first.id)
    with pytest.raises(ResourceValidationError, match="Invalid"):
        ingestion_service.complete_job(orchestration_db, first.id)
    with pytest.raises(ResourceValidationError, match="Invalid"):
        ingestion_service.retry_job(orchestration_db, first.id)

    cancelled = ingestion_service.cancel_job(
        orchestration_db,
        first.id,
        reason="No longer required",
    )
    replacement = ingestion_service.create_job(
        orchestration_db,
        {"document_id": document_id},
    )
    assert replacement.id != cancelled.id


def test_reservation_conflicts_release_and_expiry_cleanup(
    orchestration_db: Session,
) -> None:
    document_id = _eligible_document(orchestration_db)
    node = _node(orchestration_db)
    job = _queued_job(orchestration_db, document_id)
    reserved = ingestion_service.reserve_job(
        orchestration_db,
        job.id,
        node.id,
    )
    with pytest.raises(ResourceConflictError, match="active reservation"):
        ingestion_service.reserve_job(
            orchestration_db,
            job.id,
            node.id,
        )

    released = ingestion_service.release_job(
        orchestration_db,
        reserved.id,
        reason="Capacity changed",
    )
    assert released.status == "queued"
    assert released.current_reservation is None

    reserved_again = ingestion_service.reserve_job(
        orchestration_db,
        released.id,
        node.id,
    )
    active = reserved_again.current_reservation
    now = utc_now()
    active.reserved_at = now - timedelta(seconds=2)
    active.expires_at = now - timedelta(seconds=1)
    orchestration_db.commit()

    assert ingestion_service.cleanup_expired_reservations(
        orchestration_db,
        as_of=now,
    ) == 1
    cleaned = ingestion_service.get_job(
        orchestration_db,
        reserved_again.id,
    )
    assert cleaned.status == "queued"
    assert cleaned.current_reservation is None


def test_retry_limit_tracks_retries_across_attempts(
    orchestration_db: Session,
) -> None:
    document_id = _eligible_document(orchestration_db)
    node = _node(orchestration_db)
    job = _queued_job(orchestration_db, document_id)
    ingestion_service.reserve_job(orchestration_db, job.id, node.id)
    ingestion_service.start_job(orchestration_db, job.id)
    failed = ingestion_service.fail_job(
        orchestration_db,
        job.id,
        "Transient metadata service failure",
    )
    assert failed.status == "failed"
    assert failed.attempts[0].status == "failed"

    retrying = ingestion_service.retry_job(
        orchestration_db,
        job.id,
        retry_limit=1,
    )
    assert retrying.status == "retrying"
    ingestion_service.reserve_job(orchestration_db, job.id, node.id)
    ingestion_service.start_job(orchestration_db, job.id)
    second_failure = ingestion_service.fail_job(
        orchestration_db,
        job.id,
        "Second failure",
    )
    assert [item.attempt_number for item in second_failure.attempts] == [1, 2]

    with pytest.raises(ResourceValidationError, match="limit of 1"):
        ingestion_service.retry_job(
            orchestration_db,
            job.id,
            retry_limit=1,
        )


def test_cancellation_releases_running_reservation(
    orchestration_db: Session,
) -> None:
    document_id = _eligible_document(orchestration_db)
    node = _node(orchestration_db)
    job = _queued_job(orchestration_db, document_id)
    ingestion_service.reserve_job(orchestration_db, job.id, node.id)
    ingestion_service.start_job(orchestration_db, job.id)

    cancelled = ingestion_service.cancel_job(
        orchestration_db,
        job.id,
        reason="Operator cancellation",
    )
    assert cancelled.status == "cancelled"
    assert cancelled.current_reservation is None
    assert cancelled.attempts[0].status == "failed"
    assert cancelled.audit_events[-2].event_type == "cancelled"
    assert cancelled.audit_events[-1].event_type == "released"
    with pytest.raises(ResourceValidationError, match="Invalid"):
        ingestion_service.cancel_job(orchestration_db, job.id)


def test_node_heartbeat_registration_and_job_search(
    orchestration_db: Session,
) -> None:
    first_document = _eligible_document(orchestration_db)
    second_document = _eligible_document(
        orchestration_db,
        suffix="secondary",
    )
    node = _node(orchestration_db)
    old_heartbeat = node.last_heartbeat
    refreshed = ingestion_service.heartbeat_node(
        orchestration_db,
        node.id,
    )
    assert refreshed.active is True
    assert refreshed.last_heartbeat >= old_heartbeat

    registered_again = ingestion_service.register_processing_node(
        orchestration_db,
        {
            "node_name": "node-a",
            "node_version": "1.1.0",
            "hostname": "node-a-new.internal",
        },
    )
    assert registered_again.id == node.id
    assert registered_again.node_version == "1.1.0"

    first = _queued_job(orchestration_db, first_document)
    second = _queued_job(orchestration_db, second_document)
    items, total = ingestion_service.search_jobs(
        orchestration_db,
        q="secondary",
        status=JobStatus.QUEUED,
        offset=0,
        limit=1,
    )
    assert total == 1
    assert items == [second]
    page, page_total = ingestion_service.list_jobs(
        orchestration_db,
        offset=1,
        limit=1,
        sort_by="priority",
        sort_order="asc",
    )
    assert page_total == 2
    assert len(page) == 1
    assert first.id != second.id


def test_audit_history_is_ordered_and_immutable(
    orchestration_db: Session,
) -> None:
    document_id = _eligible_document(orchestration_db)
    job = _queued_job(orchestration_db, document_id)
    history = ingestion_service.get_audit_history(
        orchestration_db,
        job.id,
    )
    assert [event.event_type for event in history] == [
        AuditEventType.CREATED.value,
        AuditEventType.QUEUED.value,
    ]
    history[0].reason = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        orchestration_db.commit()
    orchestration_db.rollback()


def test_ingestion_api_authorization_and_orchestration_flow(
    orchestration_client,
) -> None:
    client, document_id = orchestration_client
    assert client.get("/api/v1/ingestion/jobs").status_code == 401
    assert client.get(
        "/api/v1/ingestion/jobs",
        headers=_headers("learner"),
    ).status_code == 403
    assert client.post(
        "/api/v1/processing/nodes",
        json={
            "node_name": "api-node",
            "node_version": "1.0.0",
            "hostname": "api-node.internal",
        },
        headers=_headers("reviewer"),
    ).status_code == 403

    node_response = client.post(
        "/api/v1/processing/nodes",
        json={
            "node_name": "api-node",
            "node_version": "1.0.0",
            "hostname": "api-node.internal",
        },
        headers=_headers("admin"),
    )
    assert node_response.status_code == 201, node_response.text
    node_id = node_response.json()["id"]

    created = client.post(
        "/api/v1/ingestion/jobs",
        json={"document_id": document_id, "priority": 5},
        headers=_headers("admin"),
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "queued"
    job_id = created.json()["id"]
    duplicate = client.post(
        "/api/v1/ingestion/jobs",
        json={"document_id": document_id, "priority": 100},
        headers=_headers("admin"),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == job_id

    for role in ("instructor", "reviewer", "admin"):
        assert client.get(
            f"/api/v1/ingestion/jobs/{job_id}",
            headers=_headers(role),
        ).status_code == 200
    assert client.post(
        f"/api/v1/ingestion/jobs/{job_id}/reserve",
        json={"node_id": node_id},
        headers=_headers("instructor"),
    ).status_code == 403

    assert client.post(
        f"/api/v1/ingestion/jobs/{job_id}/reserve",
        json={"node_id": node_id, "ttl_seconds": 600},
        headers=_headers("admin"),
    ).status_code == 200
    assert client.post(
        f"/api/v1/ingestion/jobs/{job_id}/start",
        headers=_headers("admin"),
    ).status_code == 200
    completed = client.post(
        f"/api/v1/ingestion/jobs/{job_id}/complete",
        headers=_headers("admin"),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"

    audit = client.get(
        f"/api/v1/ingestion/jobs/{job_id}/audit",
        headers=_headers("reviewer"),
    )
    assert audit.status_code == 200
    assert audit.json()[-2]["event_type"] == "succeeded"
    nodes = client.get(
        "/api/v1/processing/nodes",
        headers=_headers("instructor"),
    )
    assert nodes.status_code == 200
    assert nodes.json()["total"] == 1

