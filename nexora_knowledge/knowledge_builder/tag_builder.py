from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Concept, Tag
from ..services import concepts as concept_service
from ..services import tags as tag_service
from ..services.exceptions import ResourceConflictError, ServiceError
from .utils import BuilderResult, contains_term, slugify


@dataclass(frozen=True)
class TagRule:
    name: str
    keywords: tuple[str, ...]
    global_tag: bool = False


TAG_RULES = (
    TagRule("beginner", ("beginner", "basic", "basics", "introduction"), True),
    TagRule("advanced", ("advanced", "complex", "institutional"), True),
    TagRule("forex", ("forex", "foreign exchange", "currency pair")),
    TagRule("crypto", ("crypto", "cryptocurrency", "bitcoin", "ethereum")),
    TagRule("stocks", ("stocks", "stock market", "equities", "shares")),
    TagRule(
        "risk",
        ("risk", "risk management", "position sizing", "stop loss", "drawdown"),
    ),
    TagRule(
        "psychology",
        ("psychology", "discipline", "fear", "greed", "emotion"),
    ),
    TagRule(
        "indicator",
        ("indicator", "rsi", "moving average", "macd", "bollinger bands"),
    ),
    TagRule("trend", ("trend", "trend analysis", "moving average")),
    TagRule("support", ("support", "support level")),
    TagRule("resistance", ("resistance", "resistance level")),
    TagRule("momentum", ("momentum", "rsi", "macd")),
    TagRule("price action", ("price action", "candlestick")),
    TagRule("technical", ("technical analysis", "chart pattern", "indicator")),
    TagRule(
        "fundamental",
        ("fundamental analysis", "earnings", "economic data", "interest rate"),
    ),
)


class TagBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        document_text: str,
        concepts: list[Concept],
    ) -> BuilderResult[Tag]:
        result: BuilderResult[Tag] = BuilderResult()
        active_rules = [
            rule
            for rule in TAG_RULES
            if any(contains_term(document_text, keyword) for keyword in rule.keywords)
        ]
        if concepts and not any(rule.name in {"beginner", "advanced"} for rule in active_rules):
            active_rules.insert(0, TAG_RULES[0])

        for rule in active_rules:
            tag = self._find(rule.name)
            if tag is None:
                try:
                    tag = tag_service.create_tag(
                        self.db,
                        {
                            "name": rule.name,
                            "slug": slugify(rule.name),
                            "description": (
                                f"Automatically inferred {rule.name} knowledge tag."
                            ),
                        },
                    )
                    result.created.append(tag)
                except ResourceConflictError:
                    tag = self._find(rule.name)
                    if tag is None:
                        result.errors.append(
                            f"Tag creation conflicted for {rule.name}"
                        )
                        continue
                    result.reused.append(tag)
                    result.duplicates_skipped += 1
                except ServiceError as exc:
                    result.errors.append(
                        f"Tag creation failed for {rule.name}: {exc}"
                    )
                    continue
            else:
                result.reused.append(tag)
                result.duplicates_skipped += 1

            targets = _target_concepts(rule, document_text, concepts)
            for concept in targets:
                if any(existing.id == tag.id for existing in concept.tags):
                    result.duplicates_skipped += 1
                    continue
                try:
                    concept_service.attach_tag(self.db, concept.id, tag.id)
                except ServiceError as exc:
                    result.errors.append(
                        f"Could not attach tag {tag.name} to {concept.title}: {exc}"
                    )
        return result

    def _find(self, name: str) -> Tag | None:
        slug = slugify(name)
        return self.db.scalar(
            select(Tag).where(
                or_(func.lower(Tag.name) == name.casefold(), Tag.slug == slug)
            )
        )


def _target_concepts(
    rule: TagRule,
    document_text: str,
    concepts: list[Concept],
) -> list[Concept]:
    if rule.global_tag:
        return concepts
    targets = [
        concept
        for concept in concepts
        if any(
            contains_term(f"{concept.title} {concept.summary or ''}", keyword)
            for keyword in rule.keywords
        )
    ]
    if targets:
        return targets
    return concepts if any(
        contains_term(document_text, keyword) for keyword in rule.keywords
    ) else []
