from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, ClassVar

from pydantic import Field, StringConstraints, field_validator, model_validator

from ..models.enums import (
    DocumentStatus,
    DocumentType,
    ProcessingStatus,
    RelationshipType,
)
from .common import (
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    SlugString,
    TitleString,
)


LanguageString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$",
    ),
]
ShortString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
VersionString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ChecksumString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
IdentifierValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
FilenameString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1024),
]
StorageKeyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
]
ExtensionString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^\.?[A-Za-z0-9][A-Za-z0-9._+-]*$",
    ),
]
Sha256String = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[A-Fa-f0-9]{64}$",
    ),
]
PublicationYear = Annotated[int, Field(ge=1000, le=9999)]


class DocumentSourceSummary(ORMResponse):
    id: int
    slug: str
    title: str
    author: str | None
    publisher: str | None
    active: bool
    archived: bool


class DocumentTagSummary(ORMResponse):
    id: int
    name: str
    slug: str


class DocumentFileCreate(ORMResponse):
    document_version_id: PositiveId | None = None
    original_filename: FilenameString
    storage_key: StorageKeyString | None = None
    mime_type: ShortString
    extension: ExtensionString
    size_bytes: int = Field(ge=0)
    page_count: int | None = Field(default=None, gt=0)
    sha256: Sha256String
    processing_status: ProcessingStatus = ProcessingStatus.PENDING


class DocumentFileRead(ORMResponse):
    id: int
    document_version_id: int
    original_filename: str
    storage_key: str | None
    mime_type: str
    extension: str
    size_bytes: int
    page_count: int | None
    sha256: str
    processing_status: str
    created_at: datetime


class DocumentVersionCreate(ORMResponse):
    version: VersionString
    checksum: ChecksumString
    change_summary: str | None = None
    release_date: date | None = None
    is_current: bool = True


class DocumentVersionRead(ORMResponse):
    id: int
    document_id: int
    version: str
    checksum: str
    change_summary: str | None
    release_date: date | None
    is_current: bool
    created_at: datetime
    files: list[DocumentFileRead]


class DocumentIdentifierCreate(ORMResponse):
    identifier_type: ShortString
    identifier_value: IdentifierValue


class DocumentIdentifierRead(ORMResponse):
    id: int
    document_id: int
    identifier_type: str
    identifier_value: str


class DocumentRelationshipCreate(ORMResponse):
    target_document_id: PositiveId
    relationship_type: RelationshipType


class DocumentRelationshipRead(ORMResponse):
    id: int
    source_document_id: int
    target_document_id: int
    relationship_type: str
    created_at: datetime


class DocumentCreate(ORMResponse):
    slug: SlugString
    source_id: PositiveId
    title: TitleString
    subtitle: TitleString | None = None
    abstract: str | None = None
    description: str | None = None
    document_type: DocumentType
    language: LanguageString = "en"
    publication_date: date | None = None
    publication_year: PublicationYear | None = None
    author_override: ShortString | None = None
    publisher_override: ShortString | None = None
    status: DocumentStatus = DocumentStatus.REGISTERED
    active: bool = True
    archived: bool = False

    @model_validator(mode="after")
    def validate_document_state(self):
        if self.active and self.archived:
            raise ValueError("An archived document cannot be active")
        if (
            self.publication_date is not None
            and self.publication_year is not None
            and self.publication_date.year != self.publication_year
        ):
            raise ValueError(
                "Publication year must match the publication date year"
            )
        if self.archived and self.status != DocumentStatus.ARCHIVED:
            raise ValueError("An archived document must have archived status")
        return self


class DocumentUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "slug",
            "source_id",
            "title",
            "document_type",
            "language",
            "status",
            "active",
            "archived",
        }
    )

    slug: SlugString | None = None
    source_id: PositiveId | None = None
    title: TitleString | None = None
    subtitle: TitleString | None = None
    abstract: str | None = None
    description: str | None = None
    document_type: DocumentType | None = None
    language: LanguageString | None = None
    publication_date: date | None = None
    publication_year: PublicationYear | None = None
    author_override: ShortString | None = None
    publisher_override: ShortString | None = None
    status: DocumentStatus | None = None
    active: bool | None = None
    archived: bool | None = None

    @model_validator(mode="after")
    def validate_document_state(self):
        if self.active is True and self.archived is True:
            raise ValueError("An archived document cannot be active")
        if (
            self.publication_date is not None
            and self.publication_year is not None
            and self.publication_date.year != self.publication_year
        ):
            raise ValueError(
                "Publication year must match the publication date year"
            )
        if (
            self.archived is True
            and "status" in self.model_fields_set
            and self.status != DocumentStatus.ARCHIVED
        ):
            raise ValueError("An archived document must have archived status")
        return self


class DocumentSummary(ORMResponse):
    id: int
    uuid: str
    slug: str
    source_id: int
    title: str
    subtitle: str | None
    document_type: str
    language: str
    publication_date: date | None
    publication_year: int | None
    author_override: str | None
    publisher_override: str | None
    status: str
    active: bool
    archived: bool
    created_at: datetime
    updated_at: datetime


class DocumentRead(DocumentSummary):
    abstract: str | None
    description: str | None
    source: DocumentSourceSummary
    versions: list[DocumentVersionRead]
    files: list[DocumentFileRead]
    identifiers: list[DocumentIdentifierRead]
    relationships: list[DocumentRelationshipRead]
    incoming_relationships: list[DocumentRelationshipRead]
    tags: list[DocumentTagSummary]


class DocumentSearch(ORMResponse):
    items: list[DocumentSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class ImportBatchCreate(ORMResponse):
    description: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_by: ShortString | None = None


class ImportBatchRead(ORMResponse):
    id: int
    batch_uuid: str
    description: str
    status: str
    created_by: str | None
    created_at: datetime
    completed_at: datetime | None


class ImportBatchSearch(ORMResponse):
    items: list[ImportBatchRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


__all__ = [
    "DocumentCreate",
    "DocumentFileCreate",
    "DocumentFileRead",
    "DocumentIdentifierCreate",
    "DocumentIdentifierRead",
    "DocumentRead",
    "DocumentRelationshipCreate",
    "DocumentRelationshipRead",
    "DocumentSearch",
    "DocumentSummary",
    "DocumentUpdate",
    "DocumentVersionCreate",
    "DocumentVersionRead",
    "ImportBatchCreate",
    "ImportBatchRead",
    "ImportBatchSearch",
]
