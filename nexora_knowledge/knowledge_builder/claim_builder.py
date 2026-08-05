from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Claim, Concept
from ..services import claims as claim_service
from ..services.exceptions import ServiceError
from .concept_builder import KNOWN_CONCEPTS
from .utils import (
    BuilderResult,
    contains_term,
    informative_sentences,
    normalize_key,
)


class ClaimBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        document_text: str,
        concepts: list[Concept],
    ) -> BuilderResult[Claim]:
        result: BuilderResult[Claim] = BuilderResult()
        existing_keys = {
            normalize_key(statement)
            for statement in self.db.scalars(select(Claim.statement))
        }
        document_keys: set[str] = set()

        for sentence in informative_sentences(document_text):
            key = normalize_key(sentence)
            if key in existing_keys or key in document_keys:
                result.duplicates_skipped += 1
                continue
            concept = _concept_for_sentence(sentence, concepts)
            if concept is None:
                continue
            document_keys.add(key)
            try:
                claim = claim_service.create_claim(
                    self.db,
                    {
                        "concept_id": concept.id,
                        "statement": sentence,
                        "claim_type": _claim_type(sentence),
                        "confidence_score": 0.7,
                        "status": "draft",
                    },
                )
                result.created.append(claim)
                existing_keys.add(key)
            except ServiceError as exc:
                result.errors.append(f"Claim creation failed: {exc}")

        if concepts and not result.created and not result.duplicates_skipped:
            result.warnings.append("No informative claims were found")
        return result


def _concept_for_sentence(
    sentence: str,
    concepts: list[Concept],
) -> Concept | None:
    matches: list[tuple[int, Concept]] = []
    for concept in concepts:
        aliases = KNOWN_CONCEPTS.get(concept.title, (concept.title,))
        matched_lengths = [
            len(alias)
            for alias in aliases
            if contains_term(sentence, alias)
        ]
        if matched_lengths:
            matches.append((max(matched_lengths), concept))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1].id))
    return matches[0][1]


def _claim_type(sentence: str) -> str:
    lowered = sentence.casefold()
    if any(marker in lowered for marker in (" is ", " are ", " refers to ")):
        return "definition"
    if any(marker in lowered for marker in (" because ", " leads to ", " results in ")):
        return "causal"
    if any(marker in lowered for marker in (" should ", " must ", " need to ")):
        return "instruction"
    return "general"
