from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AssetClass,
    Claim,
    Concept,
    Evidence,
    Indicator,
    Instrument,
    KnowledgeArticle,
    KnowledgeSection,
    Source,
    SourceAssessment,
    Strategy,
)
from ..services.exceptions import ResourceConflictError


DEMONSTRATION_SLUGS = {
    "demo-gold",
    "demo-metals",
    "demo-xauusd",
    "demo-rsi",
    "demo-london-session-strategy",
}


def seed_rich_knowledge_examples(db: Session) -> dict[str, Any]:
    """Create a small, clearly labelled demonstration dataset atomically.

    This function is never called automatically. It contains no claims about
    realized or backtested strategy performance.
    """
    existing = db.scalar(
        select(Concept.id).where(Concept.slug.in_(DEMONSTRATION_SLUGS))
    )
    if existing is not None:
        raise ResourceConflictError(
            "Demonstration rich-knowledge seed data already exists"
        )

    gold = Concept(
        title="Gold (Demonstration)",
        slug="demo-gold",
        summary="Demonstration semantic identity for gold knowledge.",
    )
    metals = Concept(
        title="Metals Asset Class (Demonstration)",
        slug="demo-metals",
    )
    xauusd = Concept(
        title="XAUUSD (Demonstration)",
        slug="demo-xauusd",
    )
    rsi = Concept(
        title="Relative Strength Index (Demonstration)",
        slug="demo-rsi",
    )
    london = Concept(
        title="London Session Strategy (Demonstration)",
        slug="demo-london-session-strategy",
    )

    article = KnowledgeArticle(
        concept=gold,
        title="Gold Market Knowledge — Demonstration",
        slug="demo-gold-market-knowledge",
        summary="Illustrative rich article structure; not trading advice.",
        definition=(
            "Gold is represented here only as demonstration content for the "
            "NEXORA rich-knowledge schema."
        ),
        market_context=(
            "Real market conclusions require current, reviewed source data."
        ),
    )
    article.sections.extend(
        [
            KnowledgeSection(
                section_type="definition",
                title="Demonstration definition",
                content="A structured example section about gold.",
                position=0,
            ),
            KnowledgeSection(
                section_type="risk",
                title="Demonstration risk note",
                content=(
                    "Instrument specifications and market risks must be "
                    "verified before any trading use."
                ),
                position=1,
            ),
        ]
    )

    asset_class = AssetClass(
        concept=metals,
        name="Metals (Demonstration)",
        description="Demonstration asset-class record.",
        market_structure="Varies by spot, futures, and other venues.",
        typical_participants="Illustrative participant categories only.",
        risk_profile="Prices can be volatile; verify current market conditions.",
        trading_hours_notes="Trading hours depend on venue and broker.",
    )
    instrument = Instrument(
        concept=xauusd,
        asset_class=asset_class,
        canonical_symbol="XAUUSD",
        display_name="Gold / US Dollar (Demonstration)",
        base_asset="XAU",
        quote_asset="USD",
        instrument_type="spot_reference",
        metadata_json={"demonstration": True},
    )
    indicator = Indicator(
        concept=rsi,
        name="Relative Strength Index (Demonstration)",
        abbreviation="RSI",
        indicator_family="momentum",
        calculation_method=(
            "Demonstration record; implementations must document smoothing "
            "and warm-up behavior."
        ),
        default_parameters_json={"period": 14, "demonstration": True},
        input_requirements_json={"series": ["close"]},
        interpretation=(
            "RSI interpretation is context-dependent and is not a standalone "
            "trading instruction."
        ),
    )
    strategy = Strategy(
        concept=london,
        name="London Session Strategy (Demonstration Draft)",
        strategy_family="session",
        description=(
            "A draft schema example with no invented performance claims."
        ),
        lifecycle_status="draft",
        review_status="pending",
        eligible_markets_json=["foreign_exchange"],
        timeframes_json=["demonstration_only"],
        entry_rules_json={"rules": ["Define reviewed entry conditions."]},
        exit_rules_json={"rules": ["Define reviewed exit conditions."]},
        invalidation_rules_json={
            "rules": ["Do not use until independently validated."]
        },
        risk_rules_json={
            "rules": ["Risk limits require governance approval."]
        },
        known_weaknesses=(
            "No backtest, live result, or performance claim is included."
        ),
    )

    source = Source(
        title="Demonstration Official-Style Market Reference",
        source_type="official_publication_demo",
        author="Demonstration Publisher",
        url="https://example.invalid/nexora-demonstration-source",
        license="DEMONSTRATION_ONLY",
    )
    claim = Claim(
        concept=gold,
        statement=(
            "This demonstration dataset requires source verification before "
            "any factual or trading use."
        ),
        claim_type="strategy_rule",
        lifecycle_status="draft",
        confidence_score=1.0,
        confidence_method="demonstration assertion",
        confidence_reason="The statement governs this seed dataset itself.",
    )
    evidence = Evidence(
        claim=claim,
        source=source,
        evidence_type="demonstration_reference",
        strength=1.0,
        notes="Evidence links are illustrative, not market evidence.",
    )
    assessment = SourceAssessment(
        source=source,
        authority_score=0.0,
        accuracy_score=0.0,
        transparency_score=1.0,
        relevance_score=0.0,
        overall_score=0.0,
        assessment_method="demonstration-only assessment",
        notes=(
            "Scores describe this non-factual demonstration source and must "
            "not be reused as a real source assessment."
        ),
    )

    db.add_all(
        [
            article,
            instrument,
            indicator,
            strategy,
            evidence,
            assessment,
        ]
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "demonstration": True,
        "concept_ids": {
            "gold": gold.id,
            "metals": metals.id,
            "xauusd": xauusd.id,
            "rsi": rsi.id,
            "london_strategy": london.id,
        },
        "article_id": article.id,
        "instrument_id": instrument.id,
        "indicator_id": indicator.id,
        "strategy_id": strategy.id,
        "source_id": source.id,
        "claim_id": claim.id,
        "evidence_id": evidence.id,
        "source_assessment_id": assessment.id,
    }
