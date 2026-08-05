from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexora_knowledge.database import Base
from nexora_knowledge.models import (
    AssetClass,
    CaseStudy,
    Claim,
    ClaimConflict,
    Concept,
    ConceptAlias,
    EconomicEventType,
    FAQ,
    Formula,
    Indicator,
    Instrument,
    KnowledgeArticle,
    KnowledgeReview,
    KnowledgeRevision,
    KnowledgeSection,
    Pattern,
    Source,
    SourceAssessment,
    Strategy,
)


@pytest.fixture
def rich_db() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_rich_tables_are_registered(rich_db: Session) -> None:
    tables = set(inspect(rich_db.get_bind()).get_table_names())
    assert {
        "asset_classes",
        "case_studies",
        "claim_conflicts",
        "concept_aliases",
        "economic_event_types",
        "faqs",
        "formulas",
        "indicators",
        "instruments",
        "knowledge_articles",
        "knowledge_reviews",
        "knowledge_revisions",
        "knowledge_sections",
        "patterns",
        "source_assessments",
        "strategies",
    } <= tables


def test_article_sections_faqs_and_concept_delete_behavior(
    rich_db: Session,
) -> None:
    concept = Concept(title="Gold", slug="gold")
    article = KnowledgeArticle(
        concept=concept,
        title="Gold Markets",
        slug="gold-markets",
        confidence_score=0.85,
    )
    article.sections.extend(
        [
            KnowledgeSection(
                section_type="risk",
                title="Risk",
                content="Gold can be volatile.",
                position=1,
            ),
            KnowledgeSection(
                section_type="definition",
                title="Definition",
                content="Gold is a traded metal.",
                position=0,
                metadata_json={"source": "reviewed"},
            ),
        ]
    )
    article.faqs.extend(
        [
            FAQ(question="Second?", answer="Second.", position=1),
            FAQ(question="First?", answer="First.", position=0),
        ]
    )
    rich_db.add(article)
    rich_db.commit()
    article_id = article.id
    section_ids = [section.id for section in article.sections]
    faq_ids = [faq.id for faq in article.faqs]
    concept_id = concept.id
    rich_db.expire(article, ["sections", "faqs"])

    assert [section.position for section in article.sections] == [0, 1]
    assert [faq.position for faq in article.faqs] == [0, 1]
    assert article.concept is concept
    assert concept.articles == [article]

    rich_db.delete(article)
    rich_db.commit()

    assert rich_db.get(KnowledgeArticle, article_id) is None
    assert rich_db.get(Concept, concept_id) is concept
    assert all(rich_db.get(KnowledgeSection, item_id) is None for item_id in section_ids)
    assert all(rich_db.get(FAQ, item_id) is None for item_id in faq_ids)


def test_alias_logical_uniqueness(rich_db: Session) -> None:
    concept = Concept(title="Relative Strength Index", slug="rsi")
    concept.aliases.extend(
        [
            ConceptAlias(
                alias="RSI",
                normalized_alias="rsi",
                language="en",
            ),
            ConceptAlias(
                alias="rsi",
                normalized_alias="rsi",
                language="en",
            ),
        ]
    )
    rich_db.add(concept)

    with pytest.raises(IntegrityError):
        rich_db.commit()
    rich_db.rollback()


def test_specialized_financial_relationships(rich_db: Session) -> None:
    concepts = {
        name: Concept(title=name, slug=name.casefold().replace(" ", "-"))
        for name in (
            "Metals",
            "XAUUSD",
            "RSI",
            "London Strategy",
            "Bull Flag",
            "CPI",
        )
    }
    asset_class = AssetClass(
        concept=concepts["Metals"],
        name="Metals",
        description="Metal markets.",
        market_structure="Spot and derivatives.",
        typical_participants="Producers and investors.",
        risk_profile="Variable volatility.",
        trading_hours_notes="Venue dependent.",
    )
    instrument = Instrument(
        concept=concepts["XAUUSD"],
        asset_class=asset_class,
        canonical_symbol="XAUUSD",
        display_name="Gold / US Dollar",
        instrument_type="spot",
        metadata_json={"precision_source": "broker"},
    )
    indicator = Indicator(
        concept=concepts["RSI"],
        name="Relative Strength Index",
        indicator_family="momentum",
        calculation_method="Smoothed gain/loss ratio.",
        default_parameters_json={"period": 14},
        interpretation="Context-dependent momentum measure.",
    )
    strategy = Strategy(
        concept=concepts["London Strategy"],
        name="London Session",
        strategy_family="session",
        description="Structured draft rules.",
        entry_rules_json={"all": ["session_open"]},
        exit_rules_json={"any": ["time_exit"]},
        invalidation_rules_json={"any": ["data_missing"]},
        risk_rules_json={"max_risk": "governed_value"},
    )
    pattern = Pattern(
        concept=concepts["Bull Flag"],
        name="Bull Flag",
        pattern_family="continuation",
        description="A governed pattern definition.",
        detection_rules_json={"required": ["impulse", "consolidation"]},
    )
    event_type = EconomicEventType(
        concept=concepts["CPI"],
        name="Consumer Price Index",
        affected_assets_json=["rates", "currencies"],
    )
    formula = Formula(
        concept=concepts["RSI"],
        name="RSI expression",
        expression="100 - 100 / (1 + RS)",
        variables_json={"RS": "average gain / average loss"},
        interpretation="Maps relative strength to a bounded scale.",
    )
    case_study = CaseStudy(
        concept=concepts["XAUUSD"],
        instrument=instrument,
        strategy=strategy,
        title="Illustrative London Session Review",
        event_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
        context="A non-performance demonstration.",
        lessons="Record only information available at decision time.",
    )
    rich_db.add_all([indicator, pattern, event_type, formula, case_study])
    rich_db.commit()

    assert concepts["Metals"].asset_class is asset_class
    assert concepts["XAUUSD"].instrument is instrument
    assert concepts["RSI"].indicator is indicator
    assert concepts["London Strategy"].strategy is strategy
    assert concepts["Bull Flag"].pattern is pattern
    assert concepts["CPI"].economic_event_type is event_type
    assert concepts["RSI"].formulas == [formula]
    assert case_study.instrument is instrument
    assert case_study.strategy is strategy


def test_governance_models_and_constraints(rich_db: Session) -> None:
    concept = Concept(title="Risk", slug="risk")
    claim_a = Claim(concept=concept, statement="Risk must be bounded.")
    claim_b = Claim(concept=concept, statement="Risk can be unbounded.")
    source = Source(title="Governance Reference", source_type="book")
    rich_db.add_all([claim_a, claim_b, source])
    rich_db.flush()
    rich_db.add_all(
        [
            KnowledgeReview(entity_type="concept", entity_id=concept.id),
            KnowledgeRevision(
                entity_type="concept",
                entity_id=concept.id,
                version_number=1,
                change_type="created",
                change_summary="Initial governed snapshot.",
                snapshot_json={"title": "Risk"},
            ),
            ClaimConflict(
                claim_a=claim_a,
                claim_b=claim_b,
                conflict_type="contradiction",
                description="Opposing statements.",
            ),
            SourceAssessment(
                source=source,
                authority_score=0.8,
                overall_score=0.75,
            ),
        ]
    )
    rich_db.commit()

    assert source.assessments[0].overall_score == 0.75
    assert claim_a.conflicts_as_a[0].claim_b is claim_b

    rich_db.add(
        ClaimConflict(
            claim_a_id=claim_a.id,
            claim_b_id=claim_a.id,
            conflict_type="invalid",
            description="Self conflict.",
        )
    )
    with pytest.raises(IntegrityError):
        rich_db.commit()
    rich_db.rollback()
    assert rich_db.scalar(select(ClaimConflict).where(
        ClaimConflict.conflict_type == "invalid"
    )) is None
