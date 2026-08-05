from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar


T = TypeVar("T")


@dataclass
class BuilderResult(Generic[T]):
    created: list[T] = field(default_factory=list)
    reused: list[T] = field(default_factory=list)
    duplicates_skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def all_items(self) -> list[T]:
        return [*self.created, *self.reused]


@dataclass
class KnowledgeBuildResult:
    created_categories: list[Any] = field(default_factory=list)
    created_concepts: list[Any] = field(default_factory=list)
    created_claims: list[Any] = field(default_factory=list)
    created_relationships: list[Any] = field(default_factory=list)
    created_sources: list[Any] = field(default_factory=list)
    created_tags: list[Any] = field(default_factory=list)
    statistics: dict[str, int | float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_report(self) -> dict[str, Any]:
        return {
            "created_categories": [_entity_summary(item) for item in self.created_categories],
            "created_concepts": [_entity_summary(item) for item in self.created_concepts],
            "created_claims": [_entity_summary(item) for item in self.created_claims],
            "created_relationships": [
                _entity_summary(item) for item in self.created_relationships
            ],
            "created_sources": [_entity_summary(item) for item in self.created_sources],
            "created_tags": [_entity_summary(item) for item in self.created_tags],
            "statistics": dict(self.statistics),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": self.duration_ms,
        }


class Timer:
    def __init__(self) -> None:
        self._started_at: float | None = None

    def start(self) -> "Timer":
        self._started_at = time.perf_counter()
        return self

    @property
    def elapsed_ms(self) -> float:
        if self._started_at is None:
            return 0.0
        return round((time.perf_counter() - self._started_at) * 1000, 3)


def normalize_whitespace(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_key(value: str) -> str:
    normalized = normalize_whitespace(value).casefold()
    return re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()


def slugify(value: str, default: str = "item") -> str:
    normalized = unicodedata.normalize("NFKD", normalize_whitespace(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or default


def contains_term(text: str, term: str) -> bool:
    return re.search(
        rf"(?<!\w){re.escape(term)}(?!\w)",
        text,
        flags=re.IGNORECASE,
    ) is not None


def informative_sentences(
    text: str,
    *,
    min_words: int = 5,
    min_characters: int = 25,
) -> list[str]:
    sentences: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_whitespace(raw_line)
        if not line or _looks_like_heading(line):
            continue
        line = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", line)
        for fragment in re.split(r"(?<=[.!?])\s+", line):
            sentence = normalize_whitespace(fragment)
            words = re.findall(r"\b[\w'-]+\b", sentence, flags=re.UNICODE)
            if len(sentence) < min_characters or len(words) < min_words:
                continue
            sentences.append(sentence)
    return sentences


def unique_preserving_order(values: list[str]) -> tuple[list[str], int]:
    unique: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for value in values:
        key = normalize_key(value)
        if not key or key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(normalize_whitespace(value))
    return unique, duplicates


def _looks_like_heading(line: str) -> bool:
    if line.startswith("#"):
        return True
    plain = re.sub(r"^[#>*\s]+", "", line).strip()
    words = re.findall(r"\b[\w'-]+\b", plain, flags=re.UNICODE)
    if not words:
        return True
    if len(words) <= 10 and plain.endswith(":"):
        return True
    if len(words) > 8 or re.search(r"[.!?]$", plain):
        return False
    title_like = sum(
        1
        for word in words
        if word.isupper() or (word[:1].isupper() and word[1:].islower())
    )
    return title_like / len(words) >= 0.75


def _entity_summary(entity: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for field_name in (
        "id",
        "name",
        "title",
        "statement",
        "slug",
        "source_concept_id",
        "target_concept_id",
        "relationship_type",
    ):
        if hasattr(entity, field_name):
            summary[field_name] = getattr(entity, field_name)
    return summary
