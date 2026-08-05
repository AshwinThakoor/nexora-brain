from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexora_knowledge.models.enums import (
    ClaimType,
    DifficultyLevel,
    KnowledgeLifecycleStatus,
    KnowledgeSectionType,
    ReviewStatus,
)
from nexora_knowledge.schemas import ClaimCreate
from nexora_knowledge.schemas.financial_entities import (
    InstrumentCreate,
    PatternCreate,
    StrategyCreate,
)
from nexora_knowledge.schemas.governance import (
    ClaimConflictCreate,
    SourceAssessmentCreate,
)
from nexora_knowledge.schemas.knowledge_article import (
    KnowledgeArticleCreate,
    KnowledgeSectionCreate,
)


def test_shared_enum_values_are_stable_strings() -> None:
    assert KnowledgeLifecycleStatus.PUBLISHED.value == "published"
    assert ReviewStatus.CHANGES_REQUESTED.value == "changes_requested"
    assert DifficultyLevel.PROFESSIONAL.value == "professional"
    assert ClaimType.BACKTEST_RESULT.value == "backtest_result"
    assert KnowledgeSectionType.TRADING_APPLICATION.value == "trading_application"


def test_article_and_section_schema_validation() -> None:
    article = KnowledgeArticleCreate(
        concept_id=1,
        title="Gold",
        slug="gold",
        confidence_score=0.9,
        lifecycle_status="validated",
    )
    section = KnowledgeSectionCreate(
        article_id=1,
        section_type="formula",
        title="Formula",
        content="A structured formula explanation.",
        position=0,
        metadata_json={"variables": ["x"]},
    )
    assert article.lifecycle_status is KnowledgeLifecycleStatus.VALIDATED
    assert section.section_type is KnowledgeSectionType.FORMULA

    with pytest.raises(ValidationError):
        KnowledgeArticleCreate(
            title="Invalid",
            slug="invalid",
            confidence_score=1.01,
        )
    with pytest.raises(ValidationError):
        KnowledgeSectionCreate(
            article_id=1,
            title="Invalid",
            content="Invalid position.",
            position=-1,
        )


def test_financial_structured_schema_validation() -> None:
    strategy = StrategyCreate(
        concept_id=1,
        name="London Session",
        strategy_family="session",
        description="Machine-readable draft.",
        entry_rules_json={"all": ["session_open"]},
        exit_rules_json={"any": ["time_exit"]},
        invalidation_rules_json={"any": ["missing_data"]},
        risk_rules_json={"policy": "governed"},
    )
    pattern = PatternCreate(
        concept_id=2,
        name="Bull Flag",
        pattern_family="continuation",
        description="Structured pattern.",
        detection_rules_json={"required": ["impulse"]},
    )
    instrument = InstrumentCreate(
        concept_id=3,
        asset_class_id=1,
        canonical_symbol="XAUUSD",
        display_name="Gold / US Dollar",
        instrument_type="spot",
        price_precision=2,
    )
    assert strategy.entry_rules_json["all"] == ["session_open"]
    assert pattern.detection_rules_json["required"] == ["impulse"]
    assert instrument.price_precision == 2

    with pytest.raises(ValidationError):
        StrategyCreate(
            concept_id=1,
            name="Invalid",
            strategy_family="session",
            description="Invalid JSON.",
            entry_rules_json="not-json-structure",
            exit_rules_json={},
            invalidation_rules_json={},
            risk_rules_json={},
        )


def test_claim_conflict_and_score_schemas() -> None:
    claim = ClaimCreate(
        concept_id=1,
        statement="Reviewed claim.",
        claim_type="established_fact",
        lifecycle_status="reviewed",
        confidence_score=0.75,
    )
    assessment = SourceAssessmentCreate(
        source_id=1,
        authority_score=0.9,
        accuracy_score=0.8,
    )
    assert claim.lifecycle_status is KnowledgeLifecycleStatus.REVIEWED
    assert assessment.authority_score == 0.9

    with pytest.raises(ValidationError):
        ClaimCreate(
            concept_id=1,
            statement="Invalid score.",
            confidence_score=-0.1,
        )
    with pytest.raises(ValidationError):
        SourceAssessmentCreate(source_id=1, overall_score=1.1)
    with pytest.raises(ValidationError):
        ClaimConflictCreate(
            claim_a_id=1,
            claim_b_id=1,
            conflict_type="contradiction",
            description="Invalid self conflict.",
        )
