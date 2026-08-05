from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Category
from ..services import categories as category_service
from ..services.exceptions import ResourceConflictError, ServiceError
from .utils import BuilderResult, contains_term, slugify


@dataclass(frozen=True)
class CategoryDefinition:
    name: str
    keywords: tuple[str, ...]
    parent: str | None = None


CATEGORY_DEFINITIONS = (
    CategoryDefinition(
        "Forex",
        ("forex", "foreign exchange", "currency pair", "currency market"),
        "Financial Markets",
    ),
    CategoryDefinition(
        "Stocks",
        ("stocks", "stock market", "equities", "shares"),
        "Financial Markets",
    ),
    CategoryDefinition(
        "Crypto",
        ("crypto", "cryptocurrency", "bitcoin", "ethereum", "blockchain"),
        "Financial Markets",
    ),
    CategoryDefinition(
        "Commodities",
        ("commodities", "commodity", "gold", "crude oil", "futures"),
        "Financial Markets",
    ),
    CategoryDefinition(
        "Risk Management",
        (
            "risk management",
            "position sizing",
            "stop loss",
            "risk-reward",
            "drawdown",
        ),
    ),
    CategoryDefinition(
        "Technical Analysis",
        (
            "technical analysis",
            "chart pattern",
            "price action",
            "candlestick",
            "trend analysis",
        ),
    ),
    CategoryDefinition(
        "Fundamental Analysis",
        (
            "fundamental analysis",
            "economic data",
            "earnings",
            "interest rate",
            "macroeconomic",
        ),
    ),
    CategoryDefinition(
        "Trading Psychology",
        (
            "trading psychology",
            "trader psychology",
            "discipline",
            "fear",
            "greed",
            "emotional trading",
        ),
    ),
    CategoryDefinition(
        "Order Flow",
        ("order flow", "order book", "buying pressure", "selling pressure"),
    ),
    CategoryDefinition(
        "Market Structure",
        (
            "market structure",
            "higher high",
            "lower low",
            "break of structure",
            "liquidity",
        ),
    ),
    CategoryDefinition(
        "Indicators",
        (
            "indicator",
            "rsi",
            "relative strength index",
            "moving average",
            "macd",
            "bollinger bands",
            "momentum",
        ),
    ),
    CategoryDefinition(
        "Financial Markets",
        (
            "financial markets",
            "financial market",
            "trading",
            "market",
        ),
    ),
    CategoryDefinition("General", ()),
)

CATEGORY_BY_NAME = {definition.name: definition for definition in CATEGORY_DEFINITIONS}


@dataclass
class CategoryBuildResult:
    batch: BuilderResult[Category]
    by_name: dict[str, Category]


class CategoryBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, document_text: str) -> CategoryBuildResult:
        batch: BuilderResult[Category] = BuilderResult()
        names = self.detect_categories(document_text)
        by_name: dict[str, Category] = {}

        for name in names:
            definition = CATEGORY_BY_NAME[name]
            parent = by_name.get(definition.parent) if definition.parent else None
            category = self._find(name)
            if category is not None:
                batch.reused.append(category)
                batch.duplicates_skipped += 1
                by_name[name] = category
                continue
            values = {
                "name": name,
                "slug": slugify(name),
                "description": f"Deterministic knowledge category for {name}.",
            }
            if parent is not None:
                values["parent_id"] = parent.id
            try:
                category = category_service.create_category(self.db, values)
                batch.created.append(category)
                by_name[name] = category
            except ResourceConflictError:
                category = self._find(name)
                if category is None:
                    batch.errors.append(f"Category creation conflicted for {name}")
                else:
                    batch.reused.append(category)
                    batch.duplicates_skipped += 1
                    by_name[name] = category
            except ServiceError as exc:
                batch.errors.append(f"Category creation failed for {name}: {exc}")

        return CategoryBuildResult(batch=batch, by_name=by_name)

    @staticmethod
    def detect_categories(document_text: str) -> list[str]:
        detected: set[str] = {"General"}
        for definition in CATEGORY_DEFINITIONS:
            if any(
                contains_term(document_text, keyword)
                for keyword in definition.keywords
            ):
                detected.add(definition.name)
                if definition.parent:
                    detected.add(definition.parent)

        ordered: list[str] = []
        if "Financial Markets" in detected:
            ordered.append("Financial Markets")
        ordered.extend(
            definition.name
            for definition in CATEGORY_DEFINITIONS
            if definition.name in detected
            and definition.name not in {"Financial Markets", "General"}
        )
        ordered.append("General")
        return ordered

    def _find(self, name: str) -> Category | None:
        slug = slugify(name)
        return self.db.scalar(
            select(Category).where(
                or_(
                    func.lower(Category.name) == name.casefold(),
                    Category.slug == slug,
                )
            )
        )


def category_name_for(text: str) -> str:
    for definition in CATEGORY_DEFINITIONS:
        if definition.name in {"Financial Markets", "General"}:
            continue
        if any(contains_term(text, keyword) for keyword in definition.keywords):
            return definition.name
    if any(
        contains_term(text, keyword)
        for keyword in CATEGORY_BY_NAME["Financial Markets"].keywords
    ):
        return "Financial Markets"
    return "General"
