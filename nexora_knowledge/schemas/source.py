from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, ClassVar

from pydantic import Field, StringConstraints, model_validator

from ..models.enums import SourceType, TrustLevel
from .common import (
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    PublicationYear,
    SlugString,
    TitleString,
    TypeString,
    UnitScore,
)


URLString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
]
LanguageString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$",
    ),
]
OptionalShortString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ISBNString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=10, max_length=32),
]
ChecksumString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class SourceOrganizationRead(ORMResponse):
    id: int
    name: str
    slug: str
    website: str | None
    country: str | None
    description: str | None


class SourceLicenseRead(ORMResponse):
    id: int
    name: str
    slug: str
    url: str | None
    allows_ingestion: bool
    allows_distribution: bool
    notes: str | None


class SourceAliasRead(ORMResponse):
    id: int
    alias: str


class SourceVersionCreate(ORMResponse):
    version: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=100,
        ),
    ]
    checksum: ChecksumString
    release_date: date | None = None
    notes: str | None = None


class SourceVersionRead(SourceVersionCreate):
    id: int


class SourceTagSummary(ORMResponse):
    id: int
    name: str
    slug: str


class SourceCreate(ORMResponse):
    slug: SlugString
    title: TitleString
    subtitle: TitleString | None = None
    description: str | None = None
    source_type: SourceType
    language: LanguageString = "en"
    trust_level: TrustLevel = TrustLevel.MEDIUM
    publication_date: date | None = None
    publisher: OptionalShortString | None = None
    author: OptionalShortString | None = None
    isbn: ISBNString | None = None
    doi: OptionalShortString | None = None
    url: URLString | None = None
    external_identifier: OptionalShortString | None = None
    organization_id: PositiveId | None = None
    license_id: PositiveId | None = None
    active: bool = True
    archived: bool = False

    @model_validator(mode="after")
    def validate_lifecycle(self):
        if self.active and self.archived:
            raise ValueError("An archived source cannot be active")
        return self


class SourceUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "slug",
            "title",
            "source_type",
            "language",
            "trust_level",
            "active",
            "archived",
        }
    )

    slug: SlugString | None = None
    title: TitleString | None = None
    subtitle: TitleString | None = None
    description: str | None = None
    source_type: SourceType | None = None
    language: LanguageString | None = None
    trust_level: TrustLevel | None = None
    publication_date: date | None = None
    publisher: OptionalShortString | None = None
    author: OptionalShortString | None = None
    isbn: ISBNString | None = None
    doi: OptionalShortString | None = None
    url: URLString | None = None
    external_identifier: OptionalShortString | None = None
    organization_id: PositiveId | None = None
    license_id: PositiveId | None = None
    active: bool | None = None
    archived: bool | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self):
        if self.active is True and self.archived is True:
            raise ValueError("An archived source cannot be active")
        return self


class SourceSummary(ORMResponse):
    id: int
    uuid: str
    slug: str
    title: str
    subtitle: str | None
    source_type: str
    language: str
    trust_level: str
    publication_date: date | None
    author: str | None
    organization_id: int | None
    active: bool
    archived: bool
    created_at: datetime
    updated_at: datetime


class SourceRead(SourceSummary):
    description: str | None
    publisher: str | None
    isbn: str | None
    doi: str | None
    url: str | None
    external_identifier: str | None
    license_id: int | None
    organization: SourceOrganizationRead | None
    license_record: SourceLicenseRead | None
    aliases: list[SourceAliasRead]
    versions: list[SourceVersionRead]
    tags: list[SourceTagSummary]


class SourceSearch(ORMResponse):
    items: list[SourceSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


# Compatibility schemas for the pre-registry Knowledge Graph API.
class LegacySourceCreate(ORMResponse):
    title: TitleString
    source_type: TypeString
    author: str | None = None
    publisher: str | None = None
    publication_year: PublicationYear | None = None
    url: URLString | None = None
    license: str | None = None
    quality_score: UnitScore | None = None
    trust_score: UnitScore | None = None


class LegacySourceUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"title", "source_type"}
    )

    title: TitleString | None = None
    source_type: TypeString | None = None
    author: str | None = None
    publisher: str | None = None
    publication_year: PublicationYear | None = None
    url: URLString | None = None
    license: str | None = None
    quality_score: UnitScore | None = None
    trust_score: UnitScore | None = None


class LegacySourceResponse(ORMResponse):
    id: int
    title: str
    source_type: str
    author: str | None
    publisher: str | None
    publication_year: int | None
    url: str | None
    license: str | None
    quality_score: float | None
    trust_score: float | None
    created_at: datetime
    updated_at: datetime


SourceResponse = LegacySourceResponse


__all__ = [
    "LegacySourceCreate",
    "LegacySourceResponse",
    "LegacySourceUpdate",
    "SourceAliasRead",
    "SourceCreate",
    "SourceLicenseRead",
    "SourceOrganizationRead",
    "SourceRead",
    "SourceResponse",
    "SourceSearch",
    "SourceSummary",
    "SourceTagSummary",
    "SourceUpdate",
    "SourceVersionCreate",
    "SourceVersionRead",
]
