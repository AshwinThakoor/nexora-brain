from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Category, Concept
from ..services import concepts as concept_service
from ..services.exceptions import ResourceConflictError, ServiceError
from .category_builder import category_name_for
from .utils import (
    BuilderResult,
    contains_term,
    informative_sentences,
    normalize_key,
    normalize_whitespace,
    slugify,
)


KNOWN_CONCEPTS: dict[str, tuple[str, ...]] = {
    "Financial Markets": ("financial markets", "financial market"),
    "Forex": ("forex", "foreign exchange"),
    "Stocks": ("stocks", "stock market", "equities"),
    "Crypto": ("crypto", "cryptocurrency", "cryptocurrencies"),
    "Commodities": ("commodities", "commodity market"),
    "Risk Management": ("risk management",),
    "Position Sizing": ("position sizing",),
    "Stop Loss": ("stop loss", "stop-loss"),
    "Take Profit": ("take profit", "take-profit"),
    "Risk Reward Ratio": ("risk reward ratio", "risk-reward ratio"),
    "Technical Analysis": ("technical analysis",),
    "Fundamental Analysis": ("fundamental analysis",),
    "Trading Psychology": ("trading psychology", "trader psychology"),
    "Order Flow": ("order flow",),
    "Market Structure": ("market structure",),
    "RSI": ("rsi", "relative strength index"),
    "Moving Average": ("moving average",),
    "Simple Moving Average": ("simple moving average", "sma"),
    "Exponential Moving Average": ("exponential moving average", "ema"),
    "MACD": ("macd", "moving average convergence divergence"),
    "Bollinger Bands": ("bollinger bands",),
    "Support": ("support", "support level"),
    "Resistance": ("resistance", "resistance level"),
    "Momentum": ("momentum",),
    "Trend Analysis": ("trend analysis",),
    "Price Action": ("price action",),
    "Candlestick": ("candlestick", "candlesticks"),
    "Volatility": ("volatility",),
    "Liquidity": ("liquidity",),
    "Leverage": ("leverage",),
    "Drawdown": ("drawdown",),
    "Breakout": ("breakout", "breakouts"),
    "Trading Plan": ("trading plan",),
}

STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "and",
    "are",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "can",
    "could",
    "does",
    "each",
    "for",
    "from",
    "have",
    "into",
    "its",
    "more",
    "most",
    "not",
    "often",
    "other",
    "our",
    "should",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "use",
    "used",
    "using",
    "very",
    "was",
    "were",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "you",
    "your",
}

_CAPITALIZED_PHRASE = re.compile(
    r"\b(?:[A-Z]{2,}|[A-Z][a-z]+)"
    r"(?:\s+(?:[A-Z]{2,}|[A-Z][a-z]+)){0,3}\b"
)
_WORD = re.compile(r"\b[A-Za-z][A-Za-z'-]{2,}\b")
MAX_CONCEPTS_PER_DOCUMENT = 50


@dataclass(frozen=True)
class ConceptCandidate:
    title: str
    summary: str


class ConceptBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        document_text: str,
        categories: dict[str, Category],
    ) -> BuilderResult[Concept]:
        result: BuilderResult[Concept] = BuilderResult()
        candidates, extraction_duplicates, truncated = extract_concepts(document_text)
        result.duplicates_skipped += extraction_duplicates
        if truncated:
            result.warnings.append(
                f"Concept extraction was limited to {MAX_CONCEPTS_PER_DOCUMENT} items"
            )

        for candidate in candidates:
            slug = slugify(candidate.title, default="concept")
            existing = self._find_existing(candidate.title, slug)
            if existing is not None:
                result.reused.append(existing)
                result.duplicates_skipped += 1
                continue

            category_name = category_name_for(
                f"{candidate.title} {candidate.summary}"
            )
            category = categories.get(category_name) or categories.get("General")
            values = {
                "title": candidate.title[:500],
                "slug": self._available_slug(slug),
                "summary": candidate.summary,
                "difficulty": _infer_difficulty(candidate.summary),
                "status": "draft",
                "category_id": category.id if category is not None else None,
            }
            try:
                result.created.append(
                    concept_service.create_concept(self.db, values)
                )
            except ResourceConflictError:
                existing = self._find_existing(
                    candidate.title,
                    values["slug"],
                )
                if existing is None:
                    result.errors.append(
                        f"Concept creation conflicted for {candidate.title}"
                    )
                else:
                    result.reused.append(existing)
                    result.duplicates_skipped += 1
            except ServiceError as exc:
                result.errors.append(
                    f"Concept creation failed for {candidate.title}: {exc}"
                )

        if not result.all_items:
            result.warnings.append("No usable concepts were extracted")
        return result

    def _find_existing(self, title: str, slug: str) -> Concept | None:
        return self.db.scalar(
            select(Concept).where(
                or_(
                    func.lower(Concept.title) == title.casefold(),
                    Concept.slug == slug,
                )
            )
        )

    def _available_slug(self, base_slug: str) -> str:
        if self.db.scalar(select(Concept.id).where(Concept.slug == base_slug)) is None:
            return base_slug
        suffix = 2
        while self.db.scalar(
            select(Concept.id).where(Concept.slug == f"{base_slug}-{suffix}")
        ) is not None:
            suffix += 1
        return f"{base_slug}-{suffix}"


def extract_concepts(
    document_text: str,
) -> tuple[list[ConceptCandidate], int, bool]:
    raw_titles: list[str] = []

    for canonical, aliases in KNOWN_CONCEPTS.items():
        for alias in aliases:
            occurrences = list(
                re.finditer(
                    rf"(?<!\w){re.escape(alias)}(?!\w)",
                    document_text,
                    flags=re.IGNORECASE,
                )
            )
            raw_titles.extend(canonical for _ in occurrences)

    token_counts = Counter(token.casefold() for token in _WORD.findall(document_text))
    for match in _CAPITALIZED_PHRASE.finditer(document_text):
        phrase = _strip_leading_stopwords(normalize_whitespace(match.group(0)))
        if not phrase:
            continue
        words = phrase.split()
        if len(words) == 1:
            key = words[0].casefold()
            if not words[0].isupper() and token_counts[key] < 2:
                continue
        raw_titles.append(phrase)

    important_tokens = [
        token
        for token, count in token_counts.most_common()
        if count >= 3 and token not in STOPWORDS and len(token) >= 4
    ]
    raw_titles.extend(token.title() for token in important_tokens[:12])

    lowered_tokens = [token.casefold() for token in _WORD.findall(document_text)]
    bigram_counts = Counter(zip(lowered_tokens, lowered_tokens[1:]))
    for (first, second), count in bigram_counts.most_common():
        if count < 2:
            break
        if first in STOPWORDS or second in STOPWORDS:
            continue
        raw_titles.append(f"{first.title()} {second.title()}")
        if len(raw_titles) >= MAX_CONCEPTS_PER_DOCUMENT * 3:
            break

    canonical_by_alias = {
        normalize_key(alias): canonical
        for canonical, aliases in KNOWN_CONCEPTS.items()
        for alias in (canonical, *aliases)
    }
    unique_titles: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for raw_title in raw_titles:
        cleaned = normalize_whitespace(raw_title).strip(".,:;!?()[]{}\"'")
        cleaned = _strip_leading_stopwords(cleaned)
        key = normalize_key(cleaned)
        if not key or key in STOPWORDS or len(key) < 3:
            continue
        title = canonical_by_alias.get(key, cleaned)
        canonical_key = normalize_key(title)
        if canonical_key in seen:
            duplicates += 1
            continue
        seen.add(canonical_key)
        unique_titles.append(title)

    truncated = len(unique_titles) > MAX_CONCEPTS_PER_DOCUMENT
    unique_titles = unique_titles[:MAX_CONCEPTS_PER_DOCUMENT]
    candidates = [
        ConceptCandidate(
            title=title,
            summary=_summary_for(title, document_text),
        )
        for title in unique_titles
    ]
    return candidates, duplicates, truncated


def _summary_for(title: str, document_text: str) -> str:
    aliases = KNOWN_CONCEPTS.get(title, (title,))
    sentences = informative_sentences(
        document_text,
        min_words=3,
        min_characters=15,
    )
    matching = next(
        (
            sentence
            for sentence in sentences
            if any(contains_term(sentence, alias) for alias in aliases)
        ),
        None,
    )
    if matching:
        return matching[:500]
    return f"{title} is a concept identified in the imported document."


def _strip_leading_stopwords(value: str) -> str:
    words = value.split()
    while words and words[0].casefold() in STOPWORDS:
        words.pop(0)
    return " ".join(words)


def _infer_difficulty(text: str) -> str:
    advanced_terms = ("advanced", "complex", "institutional", "professional")
    return (
        "advanced"
        if any(contains_term(text, term) for term in advanced_terms)
        else "beginner"
    )
