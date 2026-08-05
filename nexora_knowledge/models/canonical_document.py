from __future__ import annotations

import re
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CanonicalModel(BaseModel):
    """Strict base type for portable parser output."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class DocumentMetadata(CanonicalModel):
    title: str | None = None
    author: str | None = None
    authors: list[str] = Field(default_factory=list)
    subject: str | None = None
    keywords: list[str] = Field(default_factory=list)
    creator: str | None = None
    producer: str | None = None
    created_at: str | None = None
    modified_at: str | None = None
    language: str | None = None
    source_filename: str | None = None
    extension: str | None = None
    mime_type: str | None = None
    page_count: int = Field(default=0, ge=0)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "title",
        "author",
        "subject",
        "creator",
        "producer",
        "created_at",
        "modified_at",
        "language",
        "source_filename",
        "extension",
        "mime_type",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("authors", "keywords")
    @classmethod
    def normalize_text_list(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class SourceProvenance(CanonicalModel):
    """Portable coordinates linking canonical output to its source."""

    source_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list)
    paragraph_index: int | None = Field(default=None, ge=0)
    table_index: int | None = Field(default=None, ge=0)
    character_start: int | None = Field(default=None, ge=0)
    character_end: int | None = Field(default=None, ge=0)
    source_locator: str | None = None

    @field_validator("section_path")
    @classmethod
    def normalize_section_path(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @field_validator("source_locator")
    @classmethod
    def normalize_source_locator(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class Paragraph(CanonicalModel):
    text: str
    order: int = Field(default=0, ge=0)
    page_number: int | None = Field(default=None, ge=1)
    provenance: SourceProvenance | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def text_must_have_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Paragraph text cannot be empty")
        return normalized


class Table(CanonicalModel):
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    caption: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    provenance: SourceProvenance | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("headers")
    @classmethod
    def normalize_headers(cls, values: list[str]) -> list[str]:
        return [str(value).strip() for value in values]

    @field_validator("rows")
    @classmethod
    def normalize_rows(cls, rows: list[list[str]]) -> list[list[str]]:
        return [
            [str(value).strip() for value in row]
            for row in rows
        ]


class ImageReference(CanonicalModel):
    identifier: str
    source: str | None = None
    alt_text: str | None = None
    caption: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    provenance: SourceProvenance | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("identifier")
    @classmethod
    def identifier_must_have_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Image identifier cannot be empty")
        return normalized


class Reference(CanonicalModel):
    text: str
    target: str | None = None
    reference_type: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    provenance: SourceProvenance | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def reference_text_must_have_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reference text cannot be empty")
        return normalized


class Section(CanonicalModel):
    title: str | None = None
    level: int = Field(default=1, ge=1)
    order: int = Field(default=0, ge=0)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    provenance: SourceProvenance | None = None
    paragraphs: list[Paragraph] = Field(default_factory=list)
    subsections: list[Section] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def iter_paragraphs(self):
        yield from self.paragraphs
        for subsection in self.subsections:
            yield from subsection.iter_paragraphs()

    def iter_sections(self):
        yield self
        for subsection in self.subsections:
            yield from subsection.iter_sections()


class DocumentStatistics(CanonicalModel):
    page_count: int = Field(default=0, ge=0)
    section_count: int = Field(default=0, ge=0)
    paragraph_count: int = Field(default=0, ge=0)
    table_count: int = Field(default=0, ge=0)
    image_count: int = Field(default=0, ge=0)
    reference_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)


class CanonicalDocument(CanonicalModel):
    schema_version: str = "1.0"
    parser_name: str
    parser_version: str
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    content: str = ""
    sections: list[Section] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    images: list[ImageReference] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    statistics: DocumentStatistics = Field(
        default_factory=DocumentStatistics
    )

    @field_validator("schema_version", "parser_name", "parser_version")
    @classmethod
    def required_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Canonical document identifiers cannot be empty")
        return normalized

    @classmethod
    def build(
        cls,
        *,
        parser_name: str,
        parser_version: str,
        metadata: DocumentMetadata,
        content: str,
        sections: list[Section],
        tables: list[Table] | None = None,
        images: list[ImageReference] | None = None,
        references: list[Reference] | None = None,
    ) -> Self:
        document = cls(
            parser_name=parser_name,
            parser_version=parser_version,
            metadata=metadata,
            content=content.strip(),
            sections=sections,
            tables=tables or [],
            images=images or [],
            references=references or [],
        )
        document.statistics = document.calculate_statistics()
        return document

    def iter_sections(self):
        for section in self.sections:
            yield from section.iter_sections()

    def iter_paragraphs(self):
        for section in self.sections:
            yield from section.iter_paragraphs()

    def calculate_statistics(self) -> DocumentStatistics:
        text = self.content
        if not text:
            text = "\n\n".join(
                paragraph.text for paragraph in self.iter_paragraphs()
            )
        return DocumentStatistics(
            page_count=self.metadata.page_count,
            section_count=sum(1 for _ in self.iter_sections()),
            paragraph_count=sum(1 for _ in self.iter_paragraphs()),
            table_count=len(self.tables),
            image_count=len(self.images),
            reference_count=len(self.references),
            word_count=len(re.findall(r"\S+", text)),
            character_count=len(text),
        )

    def assert_valid(self) -> None:
        expected = self.calculate_statistics()
        if self.statistics != expected:
            raise ValueError(
                "Canonical document statistics do not match its content"
            )
        if self.metadata.page_count < 1:
            raise ValueError(
                "Canonical documents must report at least one page"
            )
        if not self.content.strip():
            raise ValueError(
                "Canonical documents must contain extractable text"
            )
        if not any(True for _ in self.iter_paragraphs()):
            raise ValueError(
                "Canonical documents must contain at least one paragraph"
            )


Section.model_rebuild()


__all__ = [
    "CanonicalDocument",
    "DocumentMetadata",
    "DocumentStatistics",
    "ImageReference",
    "Paragraph",
    "Reference",
    "Section",
    "SourceProvenance",
    "Table",
]
