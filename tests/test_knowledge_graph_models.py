from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexora_knowledge.database import Base
from nexora_knowledge.models import (
    Category,
    Claim,
    Concept,
    ConceptRelationship,
    Evidence,
    KnowledgeChunk,
    KnowledgeDocument,
    Source,
    Tag,
    concept_tags,
)


@pytest.fixture
def graph_db() -> Session:
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


def test_all_models_register_and_create_tables(graph_db: Session):
    table_names = set(inspect(graph_db.get_bind()).get_table_names())

    assert {
        "categories",
        "claims",
        "concept_relationships",
        "concept_tags",
        "concepts",
        "evidence",
        "knowledge_chunks",
        "knowledge_documents",
        "sources",
        "tags",
    } <= table_names


def test_category_hierarchy_and_concept_membership(graph_db: Session):
    parent = Category(name="Trading", slug="trading")
    child = Category(name="Risk Management", slug="risk-management", parent=parent)
    concept = Concept(title="Position Sizing", slug="position-sizing", category=child)
    graph_db.add_all([parent, concept])
    graph_db.commit()

    assert child.parent is parent
    assert parent.children == [child]
    assert concept.category is child
    assert child.concepts == [concept]
    assert concept.difficulty == "beginner"
    assert concept.status == "draft"
    assert concept.version == 1


def test_concept_tags_claims_and_evidence(graph_db: Session):
    concept = Concept(title="Stop Loss", slug="stop-loss")
    tag = Tag(name="Risk", slug="risk")
    source = Source(
        title="Risk Handbook",
        source_type="book",
        quality_score=0.9,
        trust_score=0.85,
    )
    claim = Claim(
        statement="Stop losses can constrain the loss on a position.",
        confidence_score=0.8,
    )
    evidence = Evidence(
        source=source,
        evidence_type="citation",
        strength=0.75,
        citation="Risk Handbook, chapter 2",
    )
    claim.evidence_records.append(evidence)
    concept.claims.append(claim)
    concept.tags.append(tag)
    graph_db.add(concept)
    graph_db.commit()

    assert concept.tags == [tag]
    assert tag.concepts == [concept]
    assert claim.concept is concept
    assert concept.claims == [claim]
    assert evidence.claim is claim
    assert evidence.source is source
    assert source.evidence_records == [evidence]
    assert claim.claim_type == "general"
    assert claim.status == "draft"


def test_outgoing_and_incoming_concept_relationships(graph_db: Session):
    source = Concept(title="Risk", slug="risk")
    target = Concept(title="Position Sizing", slug="position-sizing")
    edge = ConceptRelationship(
        source_concept=source,
        target_concept=target,
        relationship_type="includes",
        confidence_score=0.95,
    )
    graph_db.add(edge)
    graph_db.commit()

    assert source.outgoing_relationships == [edge]
    assert target.incoming_relationships == [edge]
    assert edge.source_concept is source
    assert edge.target_concept is target


def test_duplicate_relationship_triples_are_rejected(graph_db: Session):
    source = Concept(title="Risk", slug="risk")
    target = Concept(title="Position Sizing", slug="position-sizing")
    graph_db.add_all([source, target])
    graph_db.flush()
    graph_db.add_all(
        [
            ConceptRelationship(
                source_concept_id=source.id,
                target_concept_id=target.id,
                relationship_type="includes",
            ),
            ConceptRelationship(
                source_concept_id=source.id,
                target_concept_id=target.id,
                relationship_type="includes",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        graph_db.commit()
    graph_db.rollback()


def test_duplicate_concept_tag_pairs_are_rejected(graph_db: Session):
    concept = Concept(title="Stop Loss", slug="stop-loss")
    tag = Tag(name="Risk", slug="risk")
    graph_db.add_all([concept, tag])
    graph_db.flush()
    with pytest.raises(IntegrityError):
        graph_db.execute(
            concept_tags.insert(),
            [
                {"concept_id": concept.id, "tag_id": tag.id},
                {"concept_id": concept.id, "tag_id": tag.id},
            ],
        )
        graph_db.commit()
    graph_db.rollback()


def test_pack_one_document_and_chunk_behavior_is_preserved(graph_db: Session):
    document = KnowledgeDocument(
        title="Pack 1 Document",
        file_path="knowledge_sources/pack1.txt",
        file_type="txt",
        sha256="a" * 64,
    )
    document.chunks.extend(
        [
            KnowledgeChunk(chunk_index=1, content="Second", word_count=1),
            KnowledgeChunk(chunk_index=0, content="First", word_count=1),
        ]
    )
    graph_db.add(document)
    graph_db.commit()
    document_id = document.id
    chunk_ids = [chunk.id for chunk in document.chunks]
    graph_db.expire(document, ["chunks"])

    assert [chunk.chunk_index for chunk in document.chunks] == [0, 1]
    assert document.category == "general"
    assert document.license_status == "UNKNOWN"
    assert document.quality_score == 50
    assert all(chunk.document is document for chunk in document.chunks)

    graph_db.delete(document)
    graph_db.commit()

    assert graph_db.get(KnowledgeDocument, document_id) is None
    assert all(graph_db.get(KnowledgeChunk, chunk_id) is None for chunk_id in chunk_ids)


def test_configured_graph_delete_behavior(graph_db: Session):
    category = Category(name="Trading", slug="trading")
    concept = Concept(title="Risk", slug="risk", category=category)
    related_concept = Concept(title="Stop Loss", slug="stop-loss")
    tag = Tag(name="Core", slug="core")
    source = Source(title="Handbook", source_type="book")
    claim = Claim(statement="Risk should be controlled.")
    evidence = Evidence(
        source=source,
        evidence_type="citation",
        strength=0.9,
    )
    claim.evidence_records.append(evidence)
    concept.claims.append(claim)
    concept.tags.append(tag)
    concept.outgoing_relationships.append(
        ConceptRelationship(
            target_concept=related_concept,
            relationship_type="mitigated_by",
        )
    )
    graph_db.add_all([concept, related_concept])
    graph_db.commit()
    category_id = category.id
    concept_id = concept.id
    related_concept_id = related_concept.id
    tag_id = tag.id
    source_id = source.id
    claim_id = claim.id
    evidence_id = evidence.id

    graph_db.delete(category)
    graph_db.commit()
    assert graph_db.get(Category, category_id) is None
    assert concept.category_id is None

    graph_db.delete(source)
    graph_db.commit()
    assert graph_db.get(Source, source_id) is None
    assert evidence.source_id is None

    graph_db.delete(concept)
    graph_db.commit()

    assert graph_db.get(Concept, concept_id) is None
    assert graph_db.get(Claim, claim_id) is None
    assert graph_db.get(Evidence, evidence_id) is None
    assert graph_db.get(Concept, related_concept_id) is related_concept
    assert graph_db.get(Tag, tag_id) is tag
    assert graph_db.scalar(select(func.count()).select_from(ConceptRelationship)) == 0
    assert graph_db.scalar(select(func.count()).select_from(concept_tags)) == 0
