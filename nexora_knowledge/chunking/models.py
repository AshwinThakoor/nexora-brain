from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..models.enums import ChunkContentType


class ChunkingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ChunkConfiguration(ChunkingModel):
    """Validated character-based configuration with a canonical encoding."""

    strategy_name: str = "structural"
    strategy_version: str = "1.0.0"
    target_size: int = Field(default=1200, gt=0, le=1_000_000)
    maximum_size: int = Field(default=1800, gt=0, le=1_000_000)
    minimum_size: int = Field(default=200, ge=0, le=1_000_000)
    overlap_size: int = Field(default=150, ge=0, le=1_000_000)
    boundary_preference: list[str] = Field(
        default_factory=lambda: [
            "section",
            "paragraph",
            "sentence",
            "whitespace",
            "character",
        ]
    )
    include_headings: bool = True
    include_document_title: bool = True
    preserve_tables: bool = True
    preserve_code_blocks: bool = True
    language: str | None = None
    custom_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("strategy_name", "strategy_version")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 100:
            raise ValueError(
                "Chunk strategy identifiers must contain 1 to 100 characters"
            )
        return normalized

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > 64:
            raise ValueError("Chunk language cannot exceed 64 characters")
        return normalized or None

    @field_validator("boundary_preference")
    @classmethod
    def validate_boundaries(cls, values: list[str]) -> list[str]:
        allowed = {
            "section",
            "paragraph",
            "sentence",
            "whitespace",
            "character",
        }
        normalized = [str(value).strip().casefold() for value in values]
        if not normalized or len(normalized) != len(set(normalized)):
            raise ValueError("Boundary preferences must be unique and non-empty")
        if any(value not in allowed for value in normalized):
            raise ValueError("Unsupported chunk boundary preference")
        if "character" not in normalized:
            normalized.append("character")
        return normalized

    @field_validator("custom_options")
    @classmethod
    def validate_custom_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Chunk custom options must be deterministically serializable"
            ) from exc
        return value

    @model_validator(mode="after")
    def validate_sizes(self):
        if self.maximum_size < self.target_size:
            raise ValueError("maximum_size must be at least target_size")
        if self.minimum_size > self.target_size:
            raise ValueError("minimum_size cannot exceed target_size")
        if self.overlap_size >= self.target_size:
            raise ValueError("overlap_size must be smaller than target_size")
        if self.overlap_size >= self.maximum_size:
            raise ValueError("overlap_size must be smaller than maximum_size")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def configuration_hash(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ChunkBoundary(ChunkingModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    boundary_type: str

    @model_validator(mode="after")
    def validate_order(self):
        if self.end < self.start:
            raise ValueError("Chunk boundary end cannot precede start")
        return self


class ChunkProvenance(ChunkingModel):
    source_order: int = Field(ge=0)
    canonical_block_type: str
    canonical_block_index: int | None = Field(default=None, ge=0)
    source_index: int | None = Field(default=None, ge=0)
    page_number: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list)
    paragraph_index: int | None = Field(default=None, ge=0)
    table_index: int | None = Field(default=None, ge=0)
    table_row_start: int | None = Field(default=None, ge=0)
    table_row_end: int | None = Field(default=None, ge=0)
    character_start: int | None = Field(default=None, ge=0)
    character_end: int | None = Field(default=None, ge=0)
    source_locator: str | None = None
    text_start_in_chunk: int = Field(default=0, ge=0)
    text_end_in_chunk: int = Field(default=0, ge=0)
    source_text_start: int = Field(default=0, ge=0, exclude=True)
    source_text_end: int | None = Field(default=None, ge=0, exclude=True)
    is_overlap: bool = False

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.text_end_in_chunk < self.text_start_in_chunk:
            raise ValueError("Chunk provenance text offsets are reversed")
        if (
            self.character_start is not None
            and self.character_end is not None
            and self.character_end < self.character_start
        ):
            raise ValueError("Source character offsets are reversed")
        if (
            self.table_row_start is not None
            and self.table_row_end is not None
            and self.table_row_end < self.table_row_start
        ):
            raise ValueError("Table row offsets are reversed")
        if (
            self.source_text_end is not None
            and self.source_text_end < self.source_text_start
        ):
            raise ValueError("Source text offsets are reversed")
        return self


class ChunkContentBlock(ChunkingModel):
    block_type: str
    block_index: int | None = Field(default=None, ge=0)
    text: str
    heading_context: list[str] = Field(default_factory=list)
    provenance: ChunkProvenance
    content_type: ChunkContentType = ChunkContentType.TEXT
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Chunk content blocks cannot be empty")
        return value


class ChunkCandidate(ChunkingModel):
    ordinal: int = Field(ge=0)
    text: str
    content_type: ChunkContentType = ChunkContentType.TEXT
    heading_context: list[str] = Field(default_factory=list)
    source_blocks: list[ChunkContentBlock] = Field(default_factory=list)
    provenance: list[ChunkProvenance] = Field(default_factory=list)
    character_count: int = Field(default=0, ge=0)
    estimated_word_count: int = Field(default=0, ge=0)
    content_hash: str = ""
    warnings: list[str] = Field(default_factory=list)
    overlap_metadata: dict[str, Any] | None = None
    relationship_hints: list[dict[str, Any]] = Field(default_factory=list)
    boundary: ChunkBoundary | None = None

    @model_validator(mode="after")
    def calculate_fields(self):
        if not self.text:
            raise ValueError("Text chunks cannot be empty")
        object.__setattr__(self, "character_count", len(self.text))
        object.__setattr__(
            self,
            "estimated_word_count",
            len(re.findall(r"\S+", self.text)),
        )
        if not self.content_hash:
            structural = {
                "content_type": self.content_type.value,
                "heading_context": self.heading_context,
                "text": self.text,
            }
            encoded = json.dumps(
                structural,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            object.__setattr__(
                self,
                "content_hash",
                sha256(encoded.encode("utf-8")).hexdigest(),
            )
        return self


class ChunkStatistics(ChunkingModel):
    chunk_count: int = Field(default=0, ge=0)
    total_character_count: int = Field(default=0, ge=0)
    total_word_count: int = Field(default=0, ge=0)
    minimum_chunk_size: int = Field(default=0, ge=0)
    maximum_chunk_size: int = Field(default=0, ge=0)
    overlap_character_count: int = Field(default=0, ge=0)


class ChunkingOutput(ChunkingModel):
    strategy_name: str
    strategy_version: str
    configuration_hash: str
    chunks: list[ChunkCandidate]
    statistics: ChunkStatistics
    warnings: list[str] = Field(default_factory=list)


def statistics_for(chunks: list[ChunkCandidate]) -> ChunkStatistics:
    sizes = [chunk.character_count for chunk in chunks]
    return ChunkStatistics(
        chunk_count=len(chunks),
        total_character_count=sum(sizes),
        total_word_count=sum(chunk.estimated_word_count for chunk in chunks),
        minimum_chunk_size=min(sizes, default=0),
        maximum_chunk_size=max(sizes, default=0),
        overlap_character_count=sum(
            int((chunk.overlap_metadata or {}).get("character_count", 0))
            for chunk in chunks
        ),
    )


__all__ = [
    "ChunkBoundary",
    "ChunkCandidate",
    "ChunkConfiguration",
    "ChunkContentBlock",
    "ChunkProvenance",
    "ChunkStatistics",
    "ChunkingOutput",
    "statistics_for",
]
