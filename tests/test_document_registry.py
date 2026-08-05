from __future__ import annotations

from datetime import date

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
    DocumentStatus,
    DocumentType,
    RelationshipType,
    SourceLicense,
    SourceType,
    Tag,
)
from nexora_knowledge.services import document_service, source_service
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
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
def registry_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def registry_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _enable_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        source = _source(session)
        source_id = source.id

    def override_get_db():
        with session_factory() as session:
            yield session

    monkeypatch.setattr(api_package, "init_database", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, source_id
    app.dependency_overrides.clear()
    engine.dispose()


def _headers(role: str) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": f"{role}-document-test",
        "X-Nexora-Principal-Role": role,
    }


def _source(db: Session, slug: str = "official-research"):
    license_record = SourceLicense(
        name=f"Open Licence {slug}",
        slug=f"open-licence-{slug}",
        allows_ingestion=True,
        allows_distribution=True,
    )
    db.add(license_record)
    db.commit()
    return source_service.create_source(
        db,
        {
            "slug": slug,
            "title": "Official Research Office",
            "source_type": SourceType.GOVERNMENT_REPORT,
            "language": "en",
            "trust_level": "official",
            "author": "Research Team",
            "license_id": license_record.id,
        },
    )


def _document_values(source_id: int, slug: str = "risk-report") -> dict:
    return {
        "slug": slug,
        "source_id": source_id,
        "title": "Institutional Risk Report",
        "subtitle": "Annual capital resilience review",
        "abstract": "Portfolio risk and capital controls.",
        "description": "A registered report awaiting future ingestion.",
        "document_type": DocumentType.REPORT,
        "language": "en",
        "publication_date": date(2026, 2, 1),
        "publication_year": 2026,
        "author_override": "NEXORA Research",
        "publisher_override": "NEXORA",
        "status": DocumentStatus.REGISTERED,
    }


def _file_values() -> dict:
    return {
        "original_filename": "risk-report.pdf",
        "storage_key": None,
        "mime_type": "application/pdf",
        "extension": ".PDF",
        "size_bytes": 4096,
        "page_count": 12,
        "sha256": "a" * 64,
        "processing_status": "ready",
    }


def test_document_crud_lifecycle_and_nested_metadata(
    registry_db: Session,
) -> None:
    source = _source(registry_db)
    document = document_service.register_document(
        registry_db,
        _document_values(source.id),
    )
    assert document.source is source
    assert document.status == "registered"
    assert document.active is True

    updated = document_service.update_document(
        registry_db,
        document.id,
        {"title": "Updated Institutional Risk Report"},
    )
    assert updated.title == "Updated Institutional Risk Report"

    version = document_service.register_version(
        registry_db,
        document.id,
        {"version": "1.0", "checksum": "ABC-001"},
    )
    file_record = document_service.register_file_metadata(
        registry_db,
        version.id,
        _file_values(),
    )
    identifier = document_service.add_identifier(
        registry_db,
        document.id,
        {"identifier_type": "DOI", "identifier_value": "10.1000/risk"},
    )
    loaded = document_service.get_document(registry_db, document.id)
    assert loaded.current_version is not None
    assert loaded.current_version.id == version.id
    assert [item.id for item in loaded.files] == [file_record.id]
    assert [item.id for item in loaded.identifiers] == [identifier.id]

    document_service.remove_identifier(
        registry_db,
        document.id,
        identifier.id,
    )
    assert document_service.get_document(
        registry_db,
        document.id,
    ).identifiers == []

    archived = document_service.archive_document(registry_db, document.id)
    assert archived.status == "archived"
    assert archived.archived is True
    assert archived.active is False
    restored = document_service.restore_document(registry_db, document.id)
    assert restored.status == "registered"
    assert restored.active is True
    assert restored.archived is False


def test_version_checksum_uniqueness_current_rotation_and_immutability(
    registry_db: Session,
) -> None:
    source = _source(registry_db)
    document = document_service.register_document(
        registry_db,
        _document_values(source.id),
    )
    first = document_service.register_version(
        registry_db,
        document.id,
        {"version": "1.0", "checksum": "CHECKSUM-1"},
    )
    second = document_service.register_version(
        registry_db,
        document.id,
        {"version": "2.0", "checksum": "CHECKSUM-2"},
    )
    registry_db.refresh(first)
    assert first.is_current is False
    assert second.is_current is True

    third = document_service.register_version(
        registry_db,
        document.id,
        {
            "version": "2.1-preview",
            "checksum": "CHECKSUM-3",
            "is_current": False,
        },
    )
    assert third.is_current is False
    assert document_service.get_document(
        registry_db,
        document.id,
    ).current_version.id == second.id

    promoted = document_service.set_current_version(
        registry_db,
        document.id,
        first.id,
    )
    assert promoted.is_current is True
    assert sum(
        item.is_current
        for item in document_service.get_document(
            registry_db,
            document.id,
        ).versions
    ) == 1

    with pytest.raises(ResourceConflictError, match="checksum"):
        document_service.register_version(
            registry_db,
            document.id,
            {"version": "3.0", "checksum": "checksum-1"},
        )

    promoted.checksum = "changed"
    with pytest.raises(ValueError, match="immutable"):
        registry_db.commit()
    registry_db.rollback()


def test_identifiers_relationships_and_validation(
    registry_db: Session,
) -> None:
    source = _source(registry_db)
    first = document_service.register_document(
        registry_db,
        _document_values(source.id),
    )
    second = document_service.register_document(
        registry_db,
        {
            **_document_values(source.id, "risk-report-companion"),
            "title": "Risk Report Companion",
        },
    )
    document_service.add_identifier(
        registry_db,
        first.id,
        {"identifier_type": "SEC accession", "identifier_value": "A-001"},
    )
    with pytest.raises(ResourceConflictError, match="identifier"):
        document_service.add_identifier(
            registry_db,
            second.id,
            {
                "identifier_type": "sec accession",
                "identifier_value": "a-001",
            },
        )

    relationship = document_service.create_relationship(
        registry_db,
        first.id,
        {
            "target_document_id": second.id,
            "relationship_type": RelationshipType.COMPANION,
        },
    )
    assert relationship.relationship_type == "companion"
    assert document_service.get_document(
        registry_db,
        second.id,
    ).incoming_relationships[0].id == relationship.id

    with pytest.raises(ResourceValidationError, match="itself"):
        document_service.create_relationship(
            registry_db,
            first.id,
            {
                "target_document_id": first.id,
                "relationship_type": RelationshipType.REFERENCES,
            },
        )
    with pytest.raises(ResourceConflictError, match="already exists"):
        document_service.create_relationship(
            registry_db,
            first.id,
            {
                "target_document_id": second.id,
                "relationship_type": RelationshipType.COMPANION,
            },
        )
    with pytest.raises(ResourceNotFoundError, match="Target"):
        document_service.create_relationship(
            registry_db,
            first.id,
            {
                "target_document_id": 99999,
                "relationship_type": RelationshipType.REFERENCES,
            },
        )


def test_eligibility_gate_reports_failures_and_accepts_ready_metadata(
    registry_db: Session,
) -> None:
    source = _source(registry_db)
    document = document_service.register_document(
        registry_db,
        _document_values(source.id),
    )
    with pytest.raises(ResourceValidationError, match="current version"):
        document_service.validate_ingestion_eligibility(
            registry_db,
            document.id,
        )

    version = document_service.register_version(
        registry_db,
        document.id,
        {"version": "1.0", "checksum": "eligibility-checksum"},
    )
    with pytest.raises(ResourceValidationError, match="file metadata"):
        document_service.validate_ingestion_eligibility(
            registry_db,
            document.id,
        )

    document_service.register_file_metadata(
        registry_db,
        version.id,
        _file_values(),
    )
    assert document_service.validate_ingestion_eligibility(
        registry_db,
        document.id,
    )

    source.active = False
    registry_db.commit()
    with pytest.raises(ResourceValidationError, match="source is not active"):
        document_service.validate_ingestion_eligibility(
            registry_db,
            document.id,
        )


def test_document_search_filters_tags_identifiers_and_paginates(
    registry_db: Session,
) -> None:
    source = _source(registry_db)
    risk_tag = Tag(name="Risk", slug="risk")
    registry_db.add(risk_tag)
    registry_db.commit()
    first = document_service.register_document(
        registry_db,
        _document_values(source.id),
    )
    first.tags.append(risk_tag)
    registry_db.commit()
    document_service.add_identifier(
        registry_db,
        first.id,
        {"identifier_type": "FRED release ID", "identifier_value": "RISK-01"},
    )
    second = document_service.register_document(
        registry_db,
        {
            **_document_values(source.id, "market-note"),
            "title": "Market Structure Note",
            "subtitle": "Liquidity",
            "document_type": DocumentType.NOTE,
            "language": "fr",
            "publication_date": date(2025, 1, 1),
            "publication_year": 2025,
            "author_override": None,
        },
    )

    items, total = document_service.search_documents(
        registry_db,
        title="risk",
        author="NEXORA",
        language="en",
        source="official-research",
        status=DocumentStatus.REGISTERED,
        document_type=DocumentType.REPORT,
        publication_year=2026,
        identifier="RISK-01",
        tag="risk",
    )
    assert total == 1
    assert items == [first]

    paged, paged_total = document_service.search_documents(
        registry_db,
        offset=1,
        limit=1,
        sort_by="title",
        sort_order="asc",
    )
    assert paged_total == 2
    assert paged == [second]
    assert second.id != first.id


def test_document_api_crud_search_pagination_and_authorization(
    registry_client,
) -> None:
    client, source_id = registry_client
    payload = {
        **_document_values(source_id),
        "publication_date": "2026-02-01",
    }
    assert client.get("/api/v1/documents").status_code == 401
    assert client.post(
        "/api/v1/documents",
        json=payload,
        headers=_headers("reviewer"),
    ).status_code == 403

    created = client.post(
        "/api/v1/documents",
        json=payload,
        headers=_headers("admin"),
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]

    for role in ("learner", "instructor", "reviewer", "admin"):
        assert client.get(
            f"/api/v1/documents/{document_id}",
            headers=_headers(role),
        ).status_code == 200

    listing = client.get(
        "/api/v1/documents",
        params={
            "title": "Risk",
            "type": "report",
            "publication_year": 2026,
            "offset": 0,
            "limit": 1,
        },
        headers=_headers("learner"),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["skip"] == 0

    searched = client.get(
        "/api/v1/documents/search",
        params={"q": "capital resilience"},
        headers=_headers("instructor"),
    )
    assert searched.status_code == 200
    assert searched.json()["total"] == 1

    assert client.post(
        f"/api/v1/documents/{document_id}/versions",
        json={"version": "1.0", "checksum": "api-checksum"},
        headers=_headers("learner"),
    ).status_code == 403
    version = client.post(
        f"/api/v1/documents/{document_id}/versions",
        json={"version": "1.0", "checksum": "api-checksum"},
        headers=_headers("admin"),
    )
    assert version.status_code == 201
    assert version.json()["is_current"] is True

    identifier = client.post(
        f"/api/v1/documents/{document_id}/identifiers",
        json={"identifier_type": "DOI", "identifier_value": "10.1000/api"},
        headers=_headers("admin"),
    )
    assert identifier.status_code == 201

    assert client.patch(
        f"/api/v1/documents/{document_id}",
        json={"title": "Forbidden"},
        headers=_headers("instructor"),
    ).status_code == 403
    assert client.patch(
        f"/api/v1/documents/{document_id}",
        json={"title": "Updated via API"},
        headers=_headers("admin"),
    ).status_code == 200

    batches = client.get(
        "/api/v1/import-batches",
        headers=_headers("reviewer"),
    )
    assert batches.status_code == 200
    assert batches.json()["items"] == []

    assert client.delete(
        f"/api/v1/documents/{document_id}",
        headers=_headers("reviewer"),
    ).status_code == 403
    assert client.delete(
        f"/api/v1/documents/{document_id}",
        headers=_headers("admin"),
    ).status_code == 204
