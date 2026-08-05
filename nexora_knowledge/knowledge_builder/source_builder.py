from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Source
from ..services import sources as source_service
from ..services.exceptions import ServiceError
from .utils import BuilderResult, normalize_key, normalize_whitespace


SOURCE_FIELDS = {
    "title",
    "author",
    "publisher",
    "publication_year",
    "url",
    "license",
    "source_type",
    "quality_score",
    "trust_score",
}


class SourceBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, metadata: Mapping[str, Any]) -> BuilderResult[Source]:
        result: BuilderResult[Source] = BuilderResult()
        values = self._source_values(metadata)
        existing = self._find_existing(values)
        if existing is not None:
            result.reused.append(existing)
            result.duplicates_skipped += 1
            return result

        try:
            result.created.append(source_service.create_source(self.db, values))
        except (ServiceError, TypeError, ValueError) as exc:
            result.errors.append(f"Source creation failed: {exc}")
        return result

    def _source_values(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        values = {
            key: metadata[key]
            for key in SOURCE_FIELDS
            if key in metadata and metadata[key] not in (None, "")
        }
        values["title"] = _clean_value(
            values.get("title", "Untitled Document"),
            maximum=500,
        )
        values["source_type"] = _clean_value(
            values.get("source_type", "document"),
            maximum=100,
        ).casefold()

        for field_name, maximum in (
            ("author", 255),
            ("publisher", 255),
            ("url", 2048),
            ("license", 255),
        ):
            if field_name in values:
                values[field_name] = _clean_value(values[field_name], maximum=maximum)

        if "publication_year" in values:
            try:
                values["publication_year"] = int(values["publication_year"])
            except (TypeError, ValueError):
                values.pop("publication_year")
        return values

    def _find_existing(self, values: Mapping[str, Any]) -> Source | None:
        url = values.get("url")
        if url:
            match = self.db.scalar(
                select(Source).where(func.lower(Source.url) == str(url).casefold())
            )
            if match is not None:
                return match

        candidates = self.db.scalars(
            select(Source).where(
                func.lower(Source.title) == str(values["title"]).casefold(),
                func.lower(Source.source_type)
                == str(values["source_type"]).casefold(),
            )
        )
        identity_fields = (
            "title",
            "source_type",
            "author",
            "publisher",
            "publication_year",
            "url",
        )
        expected = tuple(_identity_value(values.get(field)) for field in identity_fields)
        return next(
            (
                source
                for source in candidates
                if tuple(
                    _identity_value(getattr(source, field))
                    for field in identity_fields
                )
                == expected
            ),
            None,
        )


def _clean_value(value: Any, *, maximum: int) -> str:
    return normalize_whitespace(str(value))[:maximum]


def _identity_value(value: Any) -> str:
    if value is None:
        return ""
    return normalize_key(str(value))
