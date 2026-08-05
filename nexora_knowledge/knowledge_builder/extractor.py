from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from .category_builder import CategoryBuilder
from .claim_builder import ClaimBuilder
from .concept_builder import ConceptBuilder
from .relationship_builder import RelationshipBuilder
from .source_builder import SourceBuilder
from .tag_builder import TagBuilder
from .utils import BuilderResult, KnowledgeBuildResult


class KnowledgeExtractor:
    def __init__(
        self,
        db: Session,
        *,
        source_builder: SourceBuilder | None = None,
        category_builder: CategoryBuilder | None = None,
        concept_builder: ConceptBuilder | None = None,
        claim_builder: ClaimBuilder | None = None,
        relationship_builder: RelationshipBuilder | None = None,
        tag_builder: TagBuilder | None = None,
    ) -> None:
        self.source_builder = source_builder or SourceBuilder(db)
        self.category_builder = category_builder or CategoryBuilder(db)
        self.concept_builder = concept_builder or ConceptBuilder(db)
        self.claim_builder = claim_builder or ClaimBuilder(db)
        self.relationship_builder = relationship_builder or RelationshipBuilder(db)
        self.tag_builder = tag_builder or TagBuilder(db)

    def extract(
        self,
        document_text: str,
        metadata: Mapping[str, Any],
    ) -> tuple[KnowledgeBuildResult, int]:
        result = KnowledgeBuildResult()
        duplicates_skipped = 0

        source_batch = self.source_builder.build(metadata)
        duplicates_skipped += _merge(
            result,
            source_batch,
            result.created_sources,
        )

        category_result = self.category_builder.build(document_text)
        duplicates_skipped += _merge(
            result,
            category_result.batch,
            result.created_categories,
        )

        concept_batch = self.concept_builder.build(
            document_text,
            category_result.by_name,
        )
        duplicates_skipped += _merge(
            result,
            concept_batch,
            result.created_concepts,
        )
        concepts = concept_batch.all_items

        claim_batch = self.claim_builder.build(document_text, concepts)
        duplicates_skipped += _merge(
            result,
            claim_batch,
            result.created_claims,
        )

        relationship_batch = self.relationship_builder.build(concepts)
        duplicates_skipped += _merge(
            result,
            relationship_batch,
            result.created_relationships,
        )

        tag_batch = self.tag_builder.build(document_text, concepts)
        duplicates_skipped += _merge(
            result,
            tag_batch,
            result.created_tags,
        )
        return result, duplicates_skipped


def _merge(
    result: KnowledgeBuildResult,
    batch: BuilderResult[Any],
    destination: list[Any],
) -> int:
    destination.extend(batch.created)
    result.warnings.extend(batch.warnings)
    result.errors.extend(batch.errors)
    return batch.duplicates_skipped
