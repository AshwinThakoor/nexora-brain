from datetime import datetime
from typing import ClassVar

from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    SlugString,
)


class TagCreate(ORMResponse):
    name: NameString
    slug: SlugString
    description: str | None = None


class TagUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"name", "slug"})

    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None


class TagResponse(ORMResponse):
    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime
