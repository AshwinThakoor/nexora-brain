from datetime import datetime
from typing import ClassVar

from pydantic import Field

from .common import (
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    SlugString,
    StatusString,
    TitleString,
)
from .tag import TagResponse


class ConceptCreate(ORMResponse):
    title: TitleString
    slug: SlugString
    summary: str | None = None
    description: str | None = None
    difficulty: StatusString = "beginner"
    status: StatusString = "draft"
    version: int = Field(default=1, ge=1)
    category_id: PositiveId | None = None


class ConceptUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"title", "slug", "difficulty", "status", "version"}
    )

    title: TitleString | None = None
    slug: SlugString | None = None
    summary: str | None = None
    description: str | None = None
    difficulty: StatusString | None = None
    status: StatusString | None = None
    version: int | None = Field(default=None, ge=1)
    category_id: PositiveId | None = None


class ConceptResponse(ORMResponse):
    id: int
    title: str
    slug: str
    summary: str | None
    description: str | None
    difficulty: str
    status: str
    version: int
    category_id: int | None
    created_at: datetime
    updated_at: datetime


class ConceptDetail(ConceptResponse):
    tags: list[TagResponse] = Field(default_factory=list)
