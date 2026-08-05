from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Concept, ConceptRelationship
from ..services import relationships as relationship_service
from ..services.exceptions import ResourceConflictError, ServiceError
from .utils import BuilderResult, normalize_key


@dataclass(frozen=True)
class RelationshipRule:
    source: str
    relationship_type: str
    target: str


RELATIONSHIP_RULES = (
    RelationshipRule("Forex", "belongs_to", "Financial Markets"),
    RelationshipRule("Stocks", "belongs_to", "Financial Markets"),
    RelationshipRule("Crypto", "belongs_to", "Financial Markets"),
    RelationshipRule("Commodities", "belongs_to", "Financial Markets"),
    RelationshipRule("RSI", "is_indicator", "Technical Analysis"),
    RelationshipRule("Moving Average", "is_indicator", "Technical Analysis"),
    RelationshipRule("MACD", "is_indicator", "Technical Analysis"),
    RelationshipRule("Bollinger Bands", "is_indicator", "Technical Analysis"),
    RelationshipRule("Moving Average", "used_for", "Trend Analysis"),
    RelationshipRule("Simple Moving Average", "used_for", "Trend Analysis"),
    RelationshipRule("Exponential Moving Average", "used_for", "Trend Analysis"),
    RelationshipRule("Support", "related_to", "Resistance"),
    RelationshipRule("Position Sizing", "part_of", "Risk Management"),
    RelationshipRule("Stop Loss", "used_for", "Risk Management"),
    RelationshipRule("Order Flow", "related_to", "Market Structure"),
)


class RelationshipBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        concepts: list[Concept],
    ) -> BuilderResult[ConceptRelationship]:
        result: BuilderResult[ConceptRelationship] = BuilderResult()
        concepts_by_title = {
            normalize_key(concept.title): concept for concept in concepts
        }
        seen_rules: set[tuple[int, int, str]] = set()

        for rule in RELATIONSHIP_RULES:
            source = concepts_by_title.get(normalize_key(rule.source))
            target = concepts_by_title.get(normalize_key(rule.target))
            if source is None or target is None or source.id == target.id:
                continue
            key = (source.id, target.id, rule.relationship_type)
            if key in seen_rules or self._exists(*key):
                result.duplicates_skipped += 1
                continue
            seen_rules.add(key)
            try:
                result.created.append(
                    relationship_service.create_relationship(
                        self.db,
                        {
                            "source_concept_id": source.id,
                            "target_concept_id": target.id,
                            "relationship_type": rule.relationship_type,
                            "description": (
                                f"{source.title} {rule.relationship_type.replace('_', ' ')} "
                                f"{target.title}."
                            ),
                            "confidence_score": 0.8,
                        },
                    )
                )
            except ResourceConflictError:
                result.duplicates_skipped += 1
            except ServiceError as exc:
                result.errors.append(
                    f"Relationship creation failed for "
                    f"{source.title} -> {target.title}: {exc}"
                )
        return result

    def _exists(
        self,
        source_concept_id: int,
        target_concept_id: int,
        relationship_type: str,
    ) -> bool:
        return self.db.scalar(
            select(ConceptRelationship.id).where(
                ConceptRelationship.source_concept_id == source_concept_id,
                ConceptRelationship.target_concept_id == target_concept_id,
                ConceptRelationship.relationship_type == relationship_type,
            )
        ) is not None
