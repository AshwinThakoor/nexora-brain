from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import nexora_knowledge.api as api_package
from nexora_knowledge.api import app
from nexora_knowledge.api.dependencies import get_db
from nexora_knowledge.database import Base
from nexora_knowledge.models import (
    SourceLicense,
    SourceOrganization,
    SourceType,
    Tag,
    TrustLevel,
)
from nexora_knowledge.services import source_service
from nexora_knowledge.services.exceptions import ResourceConflictError


@pytest.fixture
def registry_db() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with session_factory() as session:
            yield session

    monkeypatch.setattr(api_package, "init_database", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


def _source_values(slug: str = "risk-handbook") -> dict:
    return {
        "slug": slug,
        "title": "Risk Handbook",
        "subtitle": "Institutional Edition",
        "description": "A reference for portfolio risk controls.",
        "source_type": SourceType.BOOK,
        "language": "en",
        "trust_level": TrustLevel.HIGH,
        "publication_date": date(2026, 1, 15),
        "publisher": "NEXORA Press",
        "author": "A. Trader",
        "isbn": "978-1-4028-9462-6",
        "doi": "10.1000/NEXORA.RISK",
        "url": "https://example.test/risk-handbook",
        "external_identifier": "catalog-001",
    }


def _headers(role: str, principal: str | None = None) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": principal or f"{role}-source-test",
        "X-Nexora-Principal-Role": role,
    }


def test_registry_models_create_normalized_sqlite_tables(
    registry_db: Session,
) -> None:
    tables = set(inspect(registry_db.get_bind()).get_table_names())
    assert {
        "source_aliases",
        "source_licenses",
        "source_organizations",
        "source_tags",
        "source_versions",
        "sources",
    } <= tables

    organization = SourceOrganization(
        name="Securities Commission",
        slug="securities-commission",
        country="MU",
    )
    license_record = SourceLicense(
        name="Open Government Licence",
        slug="open-government-licence",
        allows_ingestion=True,
        allows_distribution=True,
    )
    tag = Tag(name="Risk", slug="risk")
    registry_db.add_all([organization, license_record, tag])
    registry_db.commit()

    values = _source_values()
    values.update(
        organization_id=organization.id,
        license_id=license_record.id,
    )
    source = source_service.create_source(registry_db, values)
    source_service.assign_tags(registry_db, source.id, [tag.id])
    source_service.add_alias(registry_db, source.id, "Risk Manual")
    source_service.add_version(
        registry_db,
        source.id,
        {
            "version": "2026.1",
            "checksum": "ABC123",
            "release_date": date(2026, 1, 15),
        },
    )

    loaded = source_service.get_source(registry_db, source.id)
    assert loaded.organization is organization
    assert loaded.license_record is license_record
    assert [item.slug for item in loaded.tags] == ["risk"]
    assert [item.alias for item in loaded.aliases] == ["Risk Manual"]
    assert [item.checksum for item in loaded.versions] == ["abc123"]
    assert loaded.uuid


def test_registry_service_crud_lifecycle_and_slug_lookup(
    registry_db: Session,
) -> None:
    source = source_service.create_source(registry_db, _source_values())
    assert source.active is True
    assert source.archived is False
    assert source.doi == "10.1000/nexora.risk"
    assert source_service.get_by_slug(registry_db, "RISK-HANDBOOK") is source

    updated = source_service.update_source(
        registry_db,
        source.id,
        {
            "title": "Enterprise Risk Handbook",
            "trust_level": TrustLevel.OFFICIAL,
        },
    )
    assert updated.title == "Enterprise Risk Handbook"
    assert updated.trust_level == "official"

    archived = source_service.archive_source(registry_db, source.id)
    assert archived.active is False
    assert archived.archived is True

    restored = source_service.restore_source(registry_db, source.id)
    assert restored.active is True
    assert restored.archived is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("slug", "risk-handbook", "slug"),
        ("doi", "10.1000/NEXORA.RISK", "DOI"),
        ("isbn", "978-1-4028-9462-6", "ISBN"),
    ],
)
def test_registry_rejects_duplicate_source_identifiers(
    registry_db: Session,
    field: str,
    value: str,
    message: str,
) -> None:
    source_service.create_source(registry_db, _source_values())
    duplicate = _source_values("second-source")
    duplicate["doi"] = "10.1000/second"
    duplicate["isbn"] = "978-1-4028-9462-7"
    duplicate[field] = value

    with pytest.raises(ResourceConflictError, match=message):
        source_service.create_source(registry_db, duplicate)


def test_registry_rejects_duplicate_aliases_versions_and_checksums(
    registry_db: Session,
) -> None:
    source = source_service.create_source(registry_db, _source_values())
    source_service.add_alias(registry_db, source.id, "Risk Manual")
    with pytest.raises(ResourceConflictError, match="alias"):
        source_service.add_alias(registry_db, source.id, "risk manual")

    source_service.add_version(
        registry_db,
        source.id,
        {"version": "1.0", "checksum": "ABC123"},
    )
    with pytest.raises(ResourceConflictError, match="version or checksum"):
        source_service.add_version(
            registry_db,
            source.id,
            {"version": "1.0", "checksum": "different"},
        )
    with pytest.raises(ResourceConflictError, match="version or checksum"):
        source_service.add_version(
            registry_db,
            source.id,
            {"version": "2.0", "checksum": "abc123"},
        )


def test_registry_filtering_sorting_search_and_pagination(
    registry_db: Session,
) -> None:
    organization = SourceOrganization(
        name="Official Research Office",
        slug="official-research-office",
    )
    risk_tag = Tag(name="Risk", slug="risk")
    registry_db.add_all([organization, risk_tag])
    registry_db.commit()

    first_values = _source_values("official-risk-report")
    first_values.update(
        title="Official Risk Report",
        source_type=SourceType.GOVERNMENT_REPORT,
        trust_level=TrustLevel.OFFICIAL,
        organization_id=organization.id,
        doi="10.1000/official",
        isbn="978-1-4028-9462-8",
    )
    first = source_service.create_source(registry_db, first_values)
    source_service.assign_tags(registry_db, first.id, [risk_tag.id])
    source_service.add_alias(registry_db, first.id, "Capital Safety Standard")

    second_values = _source_values("market-article")
    second_values.update(
        title="Market Article",
        source_type=SourceType.ARTICLE,
        trust_level=TrustLevel.MEDIUM,
        language="fr",
        doi="10.1000/article",
        isbn="978-1-4028-9462-9",
    )
    second = source_service.create_source(registry_db, second_values)

    items, total = source_service.search_sources(
        registry_db,
        source_type=SourceType.GOVERNMENT_REPORT,
        organization="official-research-office",
        language="en",
        trust=TrustLevel.OFFICIAL,
        tag="risk",
        active=True,
    )
    assert total == 1
    assert items == [first]

    alias_items, alias_total = source_service.search_sources(
        registry_db,
        q="Capital Safety",
    )
    assert alias_total == 1
    assert alias_items == [first]

    paged, paged_total = source_service.search_sources(
        registry_db,
        offset=1,
        limit=1,
        sort_by="title",
        sort_order="asc",
    )
    assert paged_total == 2
    assert paged == [first]


def test_registry_api_crud_pagination_search_and_authorization(
    registry_client: TestClient,
) -> None:
    payload = {
        **_source_values(),
        "publication_date": "2026-01-15",
    }
    assert registry_client.get("/api/v1/sources").status_code == 401
    assert registry_client.post(
        "/api/v1/sources",
        json=payload,
        headers=_headers("learner"),
    ).status_code == 403

    created = registry_client.post(
        "/api/v1/sources",
        json=payload,
        headers=_headers("admin"),
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    assert created.json()["slug"] == "risk-handbook"
    assert created.json()["trust_level"] == "high"

    for role in ("learner", "instructor", "reviewer", "admin"):
        response = registry_client.get(
            f"/api/v1/sources/{source_id}",
            headers=_headers(role),
        )
        assert response.status_code == 200

    listing = registry_client.get(
        "/api/v1/sources",
        params={
            "type": "book",
            "language": "en",
            "trust": "high",
            "active": True,
            "offset": 0,
            "limit": 1,
            "sort_by": "title",
            "sort_order": "asc",
        },
        headers=_headers("learner"),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["limit"] == 1
    assert listing.json()["skip"] == 0

    searched = registry_client.get(
        "/api/v1/sources/search",
        params={"q": "portfolio risk"},
        headers=_headers("reviewer"),
    )
    assert searched.status_code == 200
    assert searched.json()["total"] == 1

    assert registry_client.patch(
        f"/api/v1/sources/{source_id}",
        json={"title": "Forbidden Update"},
        headers=_headers("instructor"),
    ).status_code == 403
    updated = registry_client.patch(
        f"/api/v1/sources/{source_id}",
        json={"title": "Updated Risk Handbook"},
        headers=_headers("admin"),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Risk Handbook"

    assert registry_client.delete(
        f"/api/v1/sources/{source_id}",
        headers=_headers("reviewer"),
    ).status_code == 403
    assert registry_client.delete(
        f"/api/v1/sources/{source_id}",
        headers=_headers("admin"),
    ).status_code == 204
    archived = registry_client.get(
        f"/api/v1/sources/{source_id}",
        headers=_headers("learner"),
    )
    assert archived.json()["active"] is False
    assert archived.json()["archived"] is True


def test_registry_api_reports_duplicate_doi_isbn_and_slug(
    registry_client: TestClient,
) -> None:
    payload = {
        **_source_values(),
        "publication_date": "2026-01-15",
    }
    headers = _headers("admin")
    assert registry_client.post(
        "/api/v1/sources",
        json=payload,
        headers=headers,
    ).status_code == 201

    for field in ("slug", "doi", "isbn"):
        duplicate = {
            **payload,
            "slug": "different-source",
            "doi": "10.1000/different",
            "isbn": "978-1-4028-9463-3",
        }
        duplicate[field] = payload[field]
        response = registry_client.post(
            "/api/v1/sources",
            json=duplicate,
            headers=headers,
        )
        assert response.status_code == 409
