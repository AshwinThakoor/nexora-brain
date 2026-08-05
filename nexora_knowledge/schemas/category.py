from datetime import datetime
from typing import ClassVar

from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    SlugString,
)


class CategoryCreate(ORMResponse):
    name: NameString
    slug: SlugString
    description: str | None = None
    parent_id: PositiveId | None = None


class CategoryUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"name", "slug"})

    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None
    parent_id: PositiveId | None = None


class CategoryResponse(ORMResponse):
    id: int
    name: str
    slug: str
    description: str | None
    parent_id: int | None
    created_at: datetime
    updated_at: datetime
