from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, ClassVar, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


LICENSES = {
    "UNKNOWN",
    "PUBLIC_DOMAIN",
    "OPEN_LICENSE",
    "OWNED",
    "PRIVATE_REFERENCE",
    "RESTRICTED",
}

NameString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
TitleString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
TypeString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
StatusString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
]
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SlugString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
PositiveId = Annotated[int, Field(gt=0)]
UnitScore = Annotated[float, Field(ge=0.0, le=1.0)]
PublicationYear = Annotated[
    int,
    Field(ge=1000, le=datetime.now(timezone.utc).year),
]


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PartialUpdateModel(BaseModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_explicit_null_for_required_fields(self):
        null_fields = sorted(
            field
            for field in self.non_nullable_fields & self.model_fields_set
            if getattr(self, field) is None
        )
        if null_fields:
            raise ValueError(
                f"Fields cannot be null: {', '.join(null_fields)}"
            )
        return self


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class IngestRequest(BaseModel):
    file_path: str
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    license_status: str = "UNKNOWN"
    license_notes: str | None = None
    commercial_use_allowed: bool = False
    quality_score: int = Field(default=50, ge=0, le=100)

    @field_validator("license_status")
    @classmethod
    def validate_license(cls, value: str) -> str:
        value = value.upper()
        if value not in LICENSES:
            raise ValueError("Invalid license status")
        return value

    @field_validator("file_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = Path(value)
        if not path.exists() or not path.is_file():
            raise ValueError(f"File does not exist: {value}")
        return str(path)


class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    category: str
    chunk_index: int
    content: str
    score: int
