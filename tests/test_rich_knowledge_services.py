from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from nexora_knowledge.database import Base
from nexora_knowledge.models import Claim, Concept, Source
from nexora_knowledge.services import financial_entities as financial_service
from nexora_knowledge.services import governance as governance_service
from nexora_knowledge.services import knowledge_articles as article_service
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceValidationError,
)
from nexora_knowledge.seeds import seed_rich_knowledge_examples


@pytest.fixture
def rich_service_db() -> Session:
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


def add_concept(db: Session, title: str) -> Concept:
    concept = Concept(
        title=title,
        slug=title.casefold().replace(" ", "-").replace("/", "-"),
    )
    db.add(concept)
    db.commit()
    return concept


def test_article_alias_section_and_faq_services(rich_service_db: Session) -> None:
    concept = add_concept(rich_service_db, "Gold")
    article = article_service.create_knowledge_article(
        rich_service_db,
        {
            "concept_id": concept.id,
            "title": "Gold Knowledge",
            "slug": " Gold Knowledge ",
            "confidence_score": 0.8,
            "sections": [
                {
                    "section_type": "risk",
                    "title": "Risk",
                    "content": "Risk context.",
                    "position": 1,
                },
                {
                    "section_type": "definition",
                    "title": "Definition",
                    "content": "Definition context.",
                    "position": 0,
                },
            ],
            "faqs": [
                {
                    "question": "What is first?",
                    "answer": "The ordered first FAQ.",
                    "position": 0,
                }
            ],
        },
    )
    alias = article_service.create_concept_alias(
        rich_service_db,
        {
            "concept_id": concept.id,
            "alias": "  GOLD   SPOT ",
            "language": "en",
        },
    )

    assert article.slug == "gold-knowledge"
    assert [section.position for section in article.sections] == [0, 1]
    assert [faq.position for faq in article.faqs] == [0]
    assert alias.normalized_alias == "gold spot"

    with pytest.raises(ResourceConflictError):
        article_service.create_concept_alias(
            rich_service_db,
            {
                "concept_id": concept.id,
                "alias": "gold spot",
                "language": "en",
            },
        )


def test_financial_entity_services_and_structured_rules(
    rich_service_db: Session,
) -> None:
    concepts = {
        name: add_concept(rich_service_db, name)
        for name in (
            "Metals",
            "XAUUSD",
            "RSI",
            "London Session",
            "Bull Flag",
            "CPI",
        )
    }
    asset_class = financial_service.create_asset_class(
        rich_service_db,
        {
            "concept_id": concepts["Metals"].id,
            "name": "Metals",
            "description": "Metals asset class.",
            "market_structure": "Multiple venues.",
            "typical_participants": "Producers and investors.",
            "risk_profile": "Variable.",
            "trading_hours_notes": "Venue dependent.",
        },
    )
    instrument = financial_service.create_instrument(
        rich_service_db,
        {
            "concept_id": concepts["XAUUSD"].id,
            "asset_class_id": asset_class.id,
            "canonical_symbol": "xauusd",
            "display_name": "Gold / US Dollar",
            "instrument_type": "spot",
            "metadata_json": {"source": "broker-specific"},
        },
    )
    indicator = financial_service.create_indicator(
        rich_service_db,
        {
            "concept_id": concepts["RSI"].id,
            "name": "Relative Strength Index",
            "indicator_family": "momentum",
            "calculation_method": "Smoothed gain/loss ratio.",
            "default_parameters_json": {"period": 14},
            "interpretation": "Context-dependent momentum.",
        },
    )
    strategy = financial_service.create_strategy(
        rich_service_db,
        {
            "concept_id": concepts["London Session"].id,
            "name": "London Session",
            "strategy_family": "session",
            "description": "Draft governed rules.",
            "entry_rules_json": {"all": ["session_open"]},
            "exit_rules_json": {"any": ["time_exit"]},
            "invalidation_rules_json": {"any": ["missing_data"]},
            "risk_rules_json": {"policy": "reviewed_limits"},
        },
    )
    pattern = financial_service.create_pattern(
        rich_service_db,
        {
            "concept_id": concepts["Bull Flag"].id,
            "name": "Bull Flag",
            "pattern_family": "continuation",
            "description": "Structured detection.",
            "detection_rules_json": {"required": ["impulse", "flag"]},
        },
    )
    event_type = financial_service.create_economic_event_type(
        rich_service_db,
        {
            "concept_id": concepts["CPI"].id,
            "name": "Consumer Price Index",
            "affected_assets_json": ["currencies", "rates"],
        },
    )
    formula = financial_service.create_formula(
        rich_service_db,
        {
            "concept_id": concepts["RSI"].id,
            "name": "RSI",
            "expression": "100 - 100 / (1 + RS)",
            "variables_json": {"RS": "average gain / average loss"},
            "interpretation": "Bounded relative-strength scale.",
        },
    )
    case_study = financial_service.create_case_study(
        rich_service_db,
        {
            "concept_id": concepts["XAUUSD"].id,
            "title": "Session Review",
            "instrument_id": instrument.id,
            "strategy_id": strategy.id,
            "context": "Demonstration context.",
            "lessons": "Separate observed facts from hindsight.",
        },
    )

    assert instrument.canonical_symbol == "XAUUSD"
    assert indicator.default_parameters_json == {"period": 14}
    assert strategy.entry_rules_json["all"] == ["session_open"]
    assert pattern.detection_rules_json["required"] == ["impulse", "flag"]
    assert event_type.affected_assets_json == ["currencies", "rates"]
    assert formula.variables_json["RS"].startswith("average")
    assert case_study.instrument_id == instrument.id
    assert case_study.strategy_id == strategy.id

    with pytest.raises(ResourceValidationError):
        financial_service.create_strategy(
            rich_service_db,
            {
                "concept_id": add_concept(
                    rich_service_db,
                    "Invalid Strategy",
                ).id,
                "name": "Invalid",
                "strategy_family": "invalid",
                "description": "Missing structured rules.",
            },
        )


def test_governance_services_conflicts_revisions_and_scores(
    rich_service_db: Session,
) -> None:
    concept = add_concept(rich_service_db, "Position Sizing")
    claim_a = Claim(concept_id=concept.id, statement="Risk is capped.")
    claim_b = Claim(concept_id=concept.id, statement="Risk is uncapped.")
    source = Source(title="Risk Standard", source_type="official_publication")
    rich_service_db.add_all([claim_a, claim_b, source])
    rich_service_db.commit()

    review = governance_service.create_knowledge_review(
        rich_service_db,
        {
            "entity_type": "concept",
            "entity_id": concept.id,
            "review_status": "approved",
            "reviewer": "Governance Team",
        },
    )
    revision = governance_service.create_knowledge_revision(
        rich_service_db,
        {
            "entity_type": "concept",
            "entity_id": concept.id,
            "version_number": 1,
            "change_type": "created",
            "change_summary": "Initial snapshot.",
            "snapshot_json": {"title": concept.title},
        },
    )
    conflict = governance_service.create_claim_conflict(
        rich_service_db,
        {
            "claim_a_id": claim_b.id,
            "claim_b_id": claim_a.id,
            "conflict_type": "contradiction",
            "description": "Opposing risk statements.",
        },
    )
    assessment = governance_service.create_source_assessment(
        rich_service_db,
        {
            "source_id": source.id,
            "authority_score": 0.9,
            "accuracy_score": 0.8,
            "overall_score": 0.85,
        },
    )

    assert review.entity_type == "concept"
    assert revision.snapshot_json["title"] == "Position Sizing"
    assert (conflict.claim_a_id, conflict.claim_b_id) == tuple(
        sorted((claim_a.id, claim_b.id))
    )
    assert assessment.overall_score == 0.85

    with pytest.raises(ResourceValidationError):
        governance_service.create_claim_conflict(
            rich_service_db,
            {
                "claim_a_id": claim_a.id,
                "claim_b_id": claim_a.id,
                "conflict_type": "invalid",
                "description": "Self conflict.",
            },
        )
    with pytest.raises(ResourceConflictError):
        governance_service.create_claim_conflict(
            rich_service_db,
            {
                "claim_a_id": claim_a.id,
                "claim_b_id": claim_b.id,
                "conflict_type": "duplicate",
                "description": "Duplicate reversed pair.",
            },
        )
    with pytest.raises(ResourceValidationError):
        governance_service.create_source_assessment(
            rich_service_db,
            {"source_id": source.id, "overall_score": 1.2},
        )


def test_optional_demonstration_seed_is_atomic_and_labelled(
    rich_service_db: Session,
) -> None:
    result = seed_rich_knowledge_examples(rich_service_db)

    assert result["demonstration"] is True
    assert result["article_id"] > 0
    assert result["instrument_id"] > 0
    assert result["indicator_id"] > 0
    assert result["strategy_id"] > 0
    assert result["source_assessment_id"] > 0

    with pytest.raises(ResourceConflictError):
        seed_rich_knowledge_examples(rich_service_db)
