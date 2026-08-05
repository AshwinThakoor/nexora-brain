from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from nexora_knowledge.database import Base
from nexora_knowledge.knowledge_builder import build_knowledge
from nexora_knowledge.knowledge_builder.importer import import_document
from nexora_knowledge.models import Category, Claim, Concept, ConceptRelationship, Source


@pytest.fixture
def builder_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


def test_simple_paragraph_builds_structured_knowledge(builder_db: Session):
    result = build_knowledge(
        (
            "Forex is a global market where currencies are traded. "
            "Risk Management helps traders control losses through Position Sizing."
        ),
        {"title": "Trading Primer", "source_type": "article"},
        db=builder_db,
    )

    assert result.errors == []
    assert result.created_sources
    assert result.created_categories
    assert result.created_concepts
    assert result.created_claims
    assert {concept.title for concept in result.created_concepts} >= {
        "Forex",
        "Risk Management",
        "Position Sizing",
    }


def test_duplicate_concepts_are_deduplicated(builder_db: Session):
    result = build_knowledge(
        (
            "Forex traders exchange currencies in the Forex market. "
            "Forex liquidity allows many Forex traders to participate efficiently."
        ),
        {"title": "Forex Notes", "source_type": "document"},
        db=builder_db,
    )

    forex_concepts = [
        concept
        for concept in builder_db.scalars(select(Concept))
        if concept.title == "Forex"
    ]
    assert len(forex_concepts) == 1
    assert result.statistics["duplicates_skipped"] > 0


def test_duplicate_claims_are_not_inserted(builder_db: Session):
    text = (
        "Position Sizing limits the capital exposed on each individual trade. "
        "Risk Management reduces the chance of catastrophic trading losses."
    )
    metadata = {"title": "Risk Notes", "source_type": "article"}

    first = build_knowledge(text, metadata, db=builder_db)
    second = build_knowledge(text, metadata, db=builder_db)

    assert first.created_claims
    assert second.created_claims == []
    assert builder_db.scalar(select(Claim).where(
        Claim.statement
        == "Position Sizing limits the capital exposed on each individual trade."
    )) is not None
    assert second.statistics["duplicates_skipped"] > 0


def test_category_mapping_assigns_risk_management(builder_db: Session):
    result = build_knowledge(
        (
            "Risk Management defines controls for every trading decision. "
            "Position Sizing allocates capital according to the accepted risk."
        ),
        {"title": "Risk Guide", "source_type": "book"},
        db=builder_db,
    )

    risk = next(
        concept
        for concept in result.created_concepts
        if concept.title == "Risk Management"
    )
    assert risk.category is not None
    assert risk.category.name == "Risk Management"
    assert builder_db.scalar(
        select(Category).where(Category.name == "General")
    ) is not None


def test_tag_inference_attaches_relevant_tags(builder_db: Session):
    result = build_knowledge(
        (
            "Technical Analysis uses the RSI momentum indicator to evaluate trends. "
            "Advanced traders compare RSI signals with Price Action confirmation."
        ),
        {"title": "Indicator Guide", "source_type": "article"},
        db=builder_db,
    )

    tag_names = {tag.name for tag in result.created_tags}
    assert {"advanced", "indicator", "momentum", "technical"} <= tag_names
    rsi = next(concept for concept in result.created_concepts if concept.title == "RSI")
    builder_db.refresh(rsi)
    assert {"advanced", "indicator", "momentum"} <= {
        tag.name for tag in rsi.tags
    }


def test_relationship_rules_create_unique_edges(builder_db: Session):
    text = (
        "Forex belongs to the wider Financial Markets ecosystem. "
        "Support and Resistance are related price levels used by active traders."
    )

    first = build_knowledge(
        text,
        {"title": "Market Map", "source_type": "article"},
        db=builder_db,
    )
    second = build_knowledge(
        text,
        {"title": "Market Map", "source_type": "article"},
        db=builder_db,
    )

    edge_types = {
        (
            edge.source_concept.title,
            edge.relationship_type,
            edge.target_concept.title,
        )
        for edge in first.created_relationships
    }
    assert ("Forex", "belongs_to", "Financial Markets") in edge_types
    assert ("Support", "related_to", "Resistance") in edge_types
    assert second.created_relationships == []
    assert len(list(builder_db.scalars(select(ConceptRelationship)))) == 2


def test_source_metadata_is_reused(builder_db: Session):
    metadata = {
        "title": "Trading Handbook",
        "author": "NEXORA",
        "publisher": "NEXORA Press",
        "publication_year": 2025,
        "url": "https://example.test/trading-handbook",
        "license": "OWNED",
        "source_type": "book",
    }
    text = "A Trading Plan records the rules that guide disciplined market decisions."

    first = build_knowledge(text, metadata, db=builder_db)
    second = build_knowledge(text, metadata, db=builder_db)

    assert len(first.created_sources) == 1
    assert second.created_sources == []
    sources = list(builder_db.scalars(select(Source)))
    assert len(sources) == 1
    assert sources[0].author == "NEXORA"


def test_pipeline_report_contains_all_required_counts(builder_db: Session):
    result = build_knowledge(
        (
            "Moving Average values smooth price data for Trend Analysis. "
            "Technical Analysis uses the Moving Average to identify market direction."
        ),
        {"title": "Trend Notes", "source_type": "document"},
        db=builder_db,
    )

    assert set(result.statistics) == {
        "categories_created",
        "concepts_created",
        "claims_created",
        "relationships_created",
        "tags_created",
        "sources_created",
        "duplicates_skipped",
        "processing_time_ms",
    }
    assert result.statistics["concepts_created"] == len(result.created_concepts)
    assert result.statistics["processing_time_ms"] == result.duration_ms
    assert result.duration_ms >= 0


def test_import_document_reuses_existing_parser_and_cleaner(
    builder_db: Session,
    tmp_path: Path,
):
    document = tmp_path / "test_trading.txt"
    document.write_text(
        (
            "Forex is traded through currency pairs in global Financial Markets.\n\n"
            "Risk Management protects capital through disciplined Position Sizing."
        ),
        encoding="utf-8",
    )

    result = import_document(document, db=builder_db)

    assert result.errors == []
    assert result.created_sources[0].title == "test_trading"
    assert result.created_sources[0].source_type == "txt"
    assert any(concept.title == "Forex" for concept in result.created_concepts)
