from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import nexora_knowledge.api as api_package
from nexora_knowledge.api import app
from nexora_knowledge.api.dependencies import get_db
from nexora_knowledge.database import Base


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
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
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    monkeypatch.setattr(api_package, "init_database", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _create_concept(client: TestClient, slug: str, **overrides) -> dict:
    payload = {"title": slug.replace("-", " ").title(), "slug": slug}
    payload.update(overrides)
    response = client.post("/concepts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_legacy_routes_remain_registered_and_health_works(client: TestClient):
    registered = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert {
        ("GET", "/health"),
        ("POST", "/ingest"),
        ("GET", "/search"),
        ("GET", "/stats"),
    } <= registered

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "nexora-knowledge",
        "version": "2.0.0",
    }


def test_category_crud_parent_validation_cycles_and_set_null(
    client: TestClient,
):
    missing_parent = client.post(
        "/categories",
        json={"name": "Child", "slug": "child", "parent_id": 999},
    )
    assert missing_parent.status_code == 404

    root = client.post(
        "/categories",
        json={"name": "Trading", "slug": "trading"},
    )
    assert root.status_code == 201
    root_id = root.json()["id"]

    child = client.post(
        "/categories",
        json={
            "name": "Risk Management",
            "slug": "risk-management",
            "parent_id": root_id,
        },
    )
    assert child.status_code == 201
    child_id = child.json()["id"]

    duplicate = client.post(
        "/categories",
        json={"name": "Trading", "slug": "other"},
    )
    assert duplicate.status_code == 409
    assert "detail" in duplicate.json()

    listing = client.get(
        "/categories",
        params={"parent_id": root_id, "name": "Risk", "skip": 0, "limit": 1},
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == child_id

    cycle = client.patch(
        f"/categories/{root_id}",
        json={"parent_id": child_id},
    )
    assert cycle.status_code == 422

    updated = client.patch(
        f"/categories/{child_id}",
        json={"description": "Position and loss controls"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Position and loss controls"

    assert client.delete(f"/categories/{root_id}").status_code == 204
    detached_child = client.get(f"/categories/{child_id}")
    assert detached_child.status_code == 200
    assert detached_child.json()["parent_id"] is None

    assert client.delete(f"/categories/{child_id}").status_code == 204
    assert client.get(f"/categories/{child_id}").status_code == 404


def test_concept_crud_filters_pagination_and_tag_associations(
    client: TestClient,
):
    category = client.post(
        "/categories",
        json={"name": "Risk", "slug": "risk"},
    ).json()
    tag = client.post(
        "/tags",
        json={"name": "Core", "slug": "core"},
    ).json()

    invalid_category = client.post(
        "/concepts",
        json={"title": "Invalid", "slug": "invalid", "category_id": 999},
    )
    assert invalid_category.status_code == 404

    concept = _create_concept(
        client,
        "position-sizing",
        category_id=category["id"],
        difficulty="intermediate",
        status="published",
        summary="Risk-based position allocation",
    )
    second = _create_concept(client, "stop-loss")

    duplicate = client.post(
        "/concepts",
        json={"title": "Duplicate", "slug": "position-sizing"},
    )
    assert duplicate.status_code == 409

    listing = client.get(
        "/concepts",
        params={
            "category_id": category["id"],
            "difficulty": "intermediate",
            "status": "published",
            "q": "allocation",
            "limit": 1,
        },
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["limit"] == 1
    assert listing.json()["items"][0]["id"] == concept["id"]

    attached = client.post(
        f"/concepts/{concept['id']}/tags/{tag['id']}"
    )
    assert attached.status_code == 200
    assert [item["id"] for item in attached.json()["tags"]] == [tag["id"]]
    assert (
        client.post(f"/concepts/{concept['id']}/tags/{tag['id']}").status_code
        == 200
    )

    by_tag = client.get("/concepts", params={"tag_id": tag["id"]})
    assert by_tag.json()["total"] == 1

    removed = client.delete(
        f"/concepts/{concept['id']}/tags/{tag['id']}"
    )
    assert removed.status_code == 200
    assert removed.json()["tags"] == []
    assert (
        client.delete(f"/concepts/{concept['id']}/tags/{tag['id']}").status_code
        == 404
    )

    updated = client.patch(
        f"/concepts/{concept['id']}",
        json={"title": "Risk Position Sizing", "summary": None},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Risk Position Sizing"
    assert updated.json()["summary"] is None

    assert client.get(f"/concepts/{second['id']}").status_code == 200
    assert client.delete(f"/concepts/{second['id']}").status_code == 204
    assert client.get(f"/concepts/{second['id']}").status_code == 404


def test_source_crud_filters_and_score_validation(client: TestClient):
    invalid_score = client.post(
        "/sources",
        json={
            "title": "Invalid",
            "source_type": "book",
            "quality_score": 1.1,
        },
    )
    assert invalid_score.status_code == 422

    created = client.post(
        "/sources",
        json={
            "title": "Risk Handbook",
            "source_type": "book",
            "author": "A. Trader",
            "publisher": "NEXORA Press",
            "publication_year": 2025,
            "quality_score": 0.9,
            "trust_score": 0.85,
        },
    )
    assert created.status_code == 201
    source_id = created.json()["id"]

    listing = client.get(
        "/sources",
        params={
            "source_type": "book",
            "author": "A. Trader",
            "q": "Handbook",
        },
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    updated = client.patch(
        f"/sources/{source_id}",
        json={"publisher": "Updated Press", "quality_score": None},
    )
    assert updated.status_code == 200
    assert updated.json()["publisher"] == "Updated Press"
    assert updated.json()["quality_score"] is None

    assert client.get(f"/sources/{source_id}").status_code == 200
    assert client.delete(f"/sources/{source_id}").status_code == 204
    assert client.get(f"/sources/{source_id}").status_code == 404


def test_claim_and_evidence_crud_validation_and_cascades(client: TestClient):
    concept = _create_concept(client, "risk-control")
    source = client.post(
        "/sources",
        json={"title": "Evidence Source", "source_type": "article"},
    ).json()

    invalid_claim = client.post(
        "/claims",
        json={"concept_id": 999, "statement": "Missing concept"},
    )
    assert invalid_claim.status_code == 404

    claim = client.post(
        "/claims",
        json={
            "concept_id": concept["id"],
            "statement": "Risk can be reduced through position sizing.",
            "confidence_score": 0.8,
        },
    )
    assert claim.status_code == 201
    claim_id = claim.json()["id"]

    claim_list = client.get(
        "/claims",
        params={
            "concept_id": concept["id"],
            "claim_type": "general",
            "status": "draft",
            "min_confidence_score": 0.7,
            "q": "position",
        },
    )
    assert claim_list.json()["total"] == 1
    assert len(client.get(f"/concepts/{concept['id']}/claims").json()) == 1

    updated_claim = client.patch(
        f"/claims/{claim_id}",
        json={"status": "reviewed", "confidence_score": 0.9},
    )
    assert updated_claim.status_code == 200
    assert updated_claim.json()["status"] == "reviewed"

    assert client.post(
        "/evidence",
        json={
            "claim_id": 999,
            "evidence_type": "citation",
            "strength": 0.8,
        },
    ).status_code == 404
    assert client.post(
        "/evidence",
        json={
            "claim_id": claim_id,
            "source_id": 999,
            "evidence_type": "citation",
            "strength": 0.8,
        },
    ).status_code == 404
    assert client.post(
        "/evidence",
        json={
            "claim_id": claim_id,
            "evidence_type": "citation",
            "strength": -0.1,
        },
    ).status_code == 422

    evidence = client.post(
        "/evidence",
        json={
            "claim_id": claim_id,
            "source_id": source["id"],
            "evidence_type": "citation",
            "strength": 0.8,
            "citation": "Section 2",
        },
    )
    assert evidence.status_code == 201
    evidence_id = evidence.json()["id"]

    evidence_list = client.get(
        "/evidence",
        params={
            "claim_id": claim_id,
            "source_id": source["id"],
            "evidence_type": "citation",
            "strength": 0.8,
        },
    )
    assert evidence_list.json()["total"] == 1
    assert len(client.get(f"/claims/{claim_id}").json()["evidence_records"]) == 1

    patched = client.patch(
        f"/evidence/{evidence_id}",
        json={"notes": "Corroborated", "citation": None},
    )
    assert patched.status_code == 200
    assert patched.json()["notes"] == "Corroborated"
    assert patched.json()["citation"] is None

    second_evidence = client.post(
        "/evidence",
        json={
            "claim_id": claim_id,
            "source_id": source["id"],
            "evidence_type": "observation",
            "strength": 0.7,
        },
    ).json()
    assert client.delete(f"/evidence/{second_evidence['id']}").status_code == 204
    assert client.get(f"/evidence/{second_evidence['id']}").status_code == 404

    assert client.delete(f"/sources/{source['id']}").status_code == 204
    assert client.get(f"/evidence/{evidence_id}").json()["source_id"] is None

    assert client.delete(f"/claims/{claim_id}").status_code == 204
    assert client.get(f"/claims/{claim_id}").status_code == 404
    assert client.get(f"/evidence/{evidence_id}").status_code == 404


def test_relationship_crud_conflicts_self_reference_and_filters(
    client: TestClient,
):
    source = _create_concept(client, "risk")
    target = _create_concept(client, "position-sizing")

    self_reference = client.post(
        "/relationships",
        json={
            "source_concept_id": source["id"],
            "target_concept_id": source["id"],
            "relationship_type": "includes",
        },
    )
    assert self_reference.status_code == 422

    missing_target = client.post(
        "/relationships",
        json={
            "source_concept_id": source["id"],
            "target_concept_id": 999,
            "relationship_type": "includes",
        },
    )
    assert missing_target.status_code == 404

    relationship = client.post(
        "/relationships",
        json={
            "source_concept_id": source["id"],
            "target_concept_id": target["id"],
            "relationship_type": "includes",
            "confidence_score": 0.9,
        },
    )
    assert relationship.status_code == 201
    relationship_id = relationship.json()["id"]

    duplicate = client.post(
        "/relationships",
        json={
            "source_concept_id": source["id"],
            "target_concept_id": target["id"],
            "relationship_type": "includes",
        },
    )
    assert duplicate.status_code == 409

    second = client.post(
        "/relationships",
        json={
            "source_concept_id": source["id"],
            "target_concept_id": target["id"],
            "relationship_type": "supports",
        },
    ).json()
    update_conflict = client.patch(
        f"/relationships/{second['id']}",
        json={"relationship_type": "includes"},
    )
    assert update_conflict.status_code == 409

    self_update = client.patch(
        f"/relationships/{relationship_id}",
        json={"target_concept_id": source["id"]},
    )
    assert self_update.status_code == 422

    listing = client.get(
        "/relationships",
        params={
            "source_concept_id": source["id"],
            "target_concept_id": target["id"],
            "relationship_type": "includes",
            "min_confidence_score": 0.8,
        },
    )
    assert listing.json()["total"] == 1
    assert (
        len(client.get(f"/concepts/{target['id']}/relationships").json()) == 2
    )

    updated = client.patch(
        f"/relationships/{relationship_id}",
        json={"description": "Contains this risk control"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Contains this risk control"

    assert client.delete(f"/relationships/{relationship_id}").status_code == 204
    assert client.get(f"/relationships/{relationship_id}").status_code == 404


def test_tag_crud_duplicates_and_delete_preserves_concept(client: TestClient):
    tag = client.post(
        "/tags",
        json={"name": "Foundational", "slug": "foundational"},
    )
    assert tag.status_code == 201
    tag_id = tag.json()["id"]

    assert client.post(
        "/tags",
        json={"name": "Foundational", "slug": "different"},
    ).status_code == 409
    assert client.post(
        "/tags",
        json={"name": "Different", "slug": "foundational"},
    ).status_code == 409

    listing = client.get("/tags", params={"q": "found", "limit": 1})
    assert listing.json()["total"] == 1
    assert client.get(f"/tags/{tag_id}").status_code == 200

    updated = client.patch(
        f"/tags/{tag_id}",
        json={"description": "Core graph knowledge"},
    )
    assert updated.status_code == 200

    concept = _create_concept(client, "tagged-concept")
    assert client.post(
        f"/concepts/{concept['id']}/tags/{tag_id}"
    ).status_code == 200
    assert client.delete(f"/tags/{tag_id}").status_code == 204
    assert client.get(f"/tags/{tag_id}").status_code == 404
    remaining = client.get(f"/concepts/{concept['id']}")
    assert remaining.status_code == 200
    assert remaining.json()["tags"] == []


def test_generic_not_found_and_pagination_validation(client: TestClient):
    assert client.get("/categories/999").status_code == 404
    assert client.get("/concepts", params={"skip": -1}).status_code == 422
    assert client.get("/sources", params={"limit": 201}).status_code == 422
