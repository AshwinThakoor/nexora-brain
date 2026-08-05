from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from nexora_knowledge.database import Base
from nexora_knowledge.services import categories as category_service
from nexora_knowledge.services import claims as claim_service
from nexora_knowledge.services import concepts as concept_service
from nexora_knowledge.services import evidence as evidence_service
from nexora_knowledge.services import relationships as relationship_service
from nexora_knowledge.services import sources as source_service
from nexora_knowledge.services import tags as tag_service
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


@pytest.fixture
def service_db() -> Session:
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


def test_category_service_crud_filtering_conflicts_and_cycles(
    service_db: Session,
):
    root = category_service.create_category(
        service_db,
        {"name": "Trading", "slug": "trading"},
    )
    child = category_service.create_category(
        service_db,
        {
            "name": "Risk",
            "slug": "risk",
            "parent_id": root.id,
        },
    )

    items, total = category_service.list_categories(
        service_db,
        parent_id=root.id,
        name="Ris",
        skip=0,
        limit=10,
    )
    assert total == 1
    assert items == [child]
    assert category_service.get_category(service_db, root.id) is root

    updated = category_service.update_category(
        service_db,
        child.id,
        {"description": "Risk controls"},
    )
    assert updated.description == "Risk controls"

    with pytest.raises(ResourceValidationError, match="cycle"):
        category_service.update_category(
            service_db,
            root.id,
            {"parent_id": child.id},
        )
    with pytest.raises(ResourceNotFoundError):
        category_service.update_category(
            service_db,
            child.id,
            {"parent_id": 999},
        )
    with pytest.raises(ResourceConflictError):
        category_service.create_category(
            service_db,
            {"name": "Trading", "slug": "another"},
        )
    with pytest.raises(ResourceNotFoundError):
        category_service.get_category(service_db, 999)

    category_service.delete_category(service_db, root.id)
    assert category_service.get_category(service_db, child.id).parent_id is None
    category_service.delete_category(service_db, child.id)
    with pytest.raises(ResourceNotFoundError):
        category_service.get_category(service_db, child.id)


def test_concept_and_tag_services_crud_filters_and_associations(
    service_db: Session,
):
    category = category_service.create_category(
        service_db,
        {"name": "Trading", "slug": "trading"},
    )
    tag = tag_service.create_tag(
        service_db,
        {"name": "Core", "slug": "core"},
    )
    concept = concept_service.create_concept(
        service_db,
        {
            "title": "Position Sizing",
            "slug": "position-sizing",
            "summary": "Risk allocation",
            "category_id": category.id,
            "difficulty": "intermediate",
            "status": "published",
        },
    )
    second = concept_service.create_concept(
        service_db,
        {"title": "Stop Loss", "slug": "stop-loss"},
    )

    concept_service.attach_tag(service_db, concept.id, tag.id)
    concept_service.attach_tag(service_db, concept.id, tag.id)
    assert [item.id for item in concept_service.get_concept(
        service_db,
        concept.id,
    ).tags] == [tag.id]

    items, total = concept_service.list_concepts(
        service_db,
        category_id=category.id,
        difficulty="intermediate",
        status="published",
        tag_id=tag.id,
        q="allocation",
        skip=0,
        limit=1,
    )
    assert total == 1
    assert items == [concept]

    updated = concept_service.update_concept(
        service_db,
        concept.id,
        {"summary": None, "title": "Risk Position Sizing"},
    )
    assert updated.summary is None
    assert updated.title == "Risk Position Sizing"

    with pytest.raises(ResourceConflictError):
        concept_service.update_concept(
            service_db,
            second.id,
            {"slug": "position-sizing"},
        )
    with pytest.raises(ResourceNotFoundError):
        concept_service.create_concept(
            service_db,
            {"title": "Invalid", "slug": "invalid", "category_id": 999},
        )

    concept_service.remove_tag(service_db, concept.id, tag.id)
    with pytest.raises(ResourceNotFoundError, match="association"):
        concept_service.remove_tag(service_db, concept.id, tag.id)

    tag_items, tag_total = tag_service.list_tags(
        service_db,
        q="cor",
        skip=0,
        limit=10,
    )
    assert tag_total == 1
    assert tag_items == [tag]
    assert tag_service.update_tag(
        service_db,
        tag.id,
        {"description": "Foundational"},
    ).description == "Foundational"

    tag_service.delete_tag(service_db, tag.id)
    assert concept_service.get_concept(service_db, concept.id) is not None
    concept_service.delete_concept(service_db, second.id)
    with pytest.raises(ResourceNotFoundError):
        concept_service.get_concept(service_db, second.id)


def test_source_claim_and_evidence_services_crud_and_cascades(
    service_db: Session,
):
    concept = concept_service.create_concept(
        service_db,
        {"title": "Risk", "slug": "risk"},
    )
    source = source_service.create_source(
        service_db,
        {
            "title": "Risk Handbook",
            "source_type": "book",
            "author": "A. Trader",
            "quality_score": 0.9,
            "trust_score": 0.8,
        },
    )
    source_items, source_total = source_service.list_sources(
        service_db,
        source_type="book",
        author="A. Trader",
        q="Handbook",
    )
    assert source_total == 1
    assert source_items == [source]
    assert source_service.update_source(
        service_db,
        source.id,
        {"publisher": "NEXORA Press"},
    ).publisher == "NEXORA Press"
    with pytest.raises(ResourceValidationError):
        source_service.update_source(
            service_db,
            source.id,
            {"quality_score": 2.0},
        )

    claim = claim_service.create_claim(
        service_db,
        {
            "concept_id": concept.id,
            "statement": "Position sizing constrains risk.",
            "confidence_score": 0.8,
        },
    )
    claim_items, claim_total = claim_service.list_claims(
        service_db,
        concept_id=concept.id,
        claim_type="general",
        status="draft",
        min_confidence_score=0.7,
        q="constrains",
    )
    assert claim_total == 1
    assert claim_items == [claim]
    assert claim_service.update_claim(
        service_db,
        claim.id,
        {"status": "reviewed"},
    ).status == "reviewed"
    with pytest.raises(ResourceNotFoundError):
        claim_service.create_claim(
            service_db,
            {"concept_id": 999, "statement": "Invalid"},
        )

    evidence = evidence_service.create_evidence(
        service_db,
        {
            "claim_id": claim.id,
            "source_id": source.id,
            "evidence_type": "citation",
            "strength": 0.9,
        },
    )
    evidence_items, evidence_total = evidence_service.list_evidence(
        service_db,
        claim_id=claim.id,
        source_id=source.id,
        evidence_type="citation",
        strength=0.9,
    )
    assert evidence_total == 1
    assert evidence_items == [evidence]
    assert evidence_service.update_evidence(
        service_db,
        evidence.id,
        {"notes": "Reviewed"},
    ).notes == "Reviewed"
    with pytest.raises(ResourceNotFoundError):
        evidence_service.create_evidence(
            service_db,
            {
                "claim_id": claim.id,
                "source_id": 999,
                "evidence_type": "citation",
                "strength": 0.5,
            },
        )

    source_service.delete_source(service_db, source.id)
    assert evidence_service.get_evidence(service_db, evidence.id).source_id is None
    evidence_service.delete_evidence(service_db, evidence.id)
    with pytest.raises(ResourceNotFoundError):
        evidence_service.get_evidence(service_db, evidence.id)
    claim_service.delete_claim(service_db, claim.id)
    with pytest.raises(ResourceNotFoundError):
        claim_service.get_claim(service_db, claim.id)


def test_relationship_service_crud_filtering_and_conflicts(
    service_db: Session,
):
    source = concept_service.create_concept(
        service_db,
        {"title": "Risk", "slug": "risk"},
    )
    target = concept_service.create_concept(
        service_db,
        {"title": "Position Sizing", "slug": "position-sizing"},
    )
    relationship = relationship_service.create_relationship(
        service_db,
        {
            "source_concept_id": source.id,
            "target_concept_id": target.id,
            "relationship_type": "includes",
            "confidence_score": 0.9,
        },
    )

    items, total = relationship_service.list_relationships(
        service_db,
        source_concept_id=source.id,
        target_concept_id=target.id,
        relationship_type="includes",
        min_confidence_score=0.8,
    )
    assert total == 1
    assert items == [relationship]
    assert relationship_service.update_relationship(
        service_db,
        relationship.id,
        {"description": "Risk includes sizing"},
    ).description == "Risk includes sizing"

    with pytest.raises(ResourceConflictError):
        relationship_service.create_relationship(
            service_db,
            {
                "source_concept_id": source.id,
                "target_concept_id": target.id,
                "relationship_type": "includes",
            },
        )
    with pytest.raises(ResourceValidationError):
        relationship_service.update_relationship(
            service_db,
            relationship.id,
            {"target_concept_id": source.id},
        )
    with pytest.raises(ResourceNotFoundError):
        relationship_service.create_relationship(
            service_db,
            {
                "source_concept_id": source.id,
                "target_concept_id": 999,
                "relationship_type": "includes",
            },
        )

    relationship_service.delete_relationship(service_db, relationship.id)
    with pytest.raises(ResourceNotFoundError):
        relationship_service.get_relationship(service_db, relationship.id)


def test_integrity_conflict_rolls_back_and_session_remains_usable(
    service_db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    tag_service.create_tag(
        service_db,
        {"name": "Core", "slug": "core"},
    )
    monkeypatch.setattr(tag_service, "_ensure_unique", lambda *args, **kwargs: None)

    with pytest.raises(ResourceConflictError):
        tag_service.create_tag(
            service_db,
            {"name": "Core", "slug": "core"},
        )

    recovered = tag_service.create_tag(
        service_db,
        {"name": "Recovered", "slug": "recovered"},
    )
    assert recovered.id is not None
