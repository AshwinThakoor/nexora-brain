from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    event,
    ForeignKey,
    Index,
    inspect,
    Integer,
    JSON,
    select,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin, utc_now
from .enums import ChunkSetStatus, ChunkingExecutionStatus


def _new_uuid() -> str:
    return str(uuid4())


class ChunkSet(TimestampMixin, Base):
    """One immutable successful strategy/configuration output."""

    __tablename__ = "chunk_sets"
    __table_args__ = (
        UniqueConstraint(
            "parse_result_id",
            "canonical_content_hash",
            "strategy_name",
            "strategy_version",
            "configuration_hash",
            name="uq_chunk_set_identity",
        ),
        Index(
            "ix_chunk_sets_parse_status",
            "parse_result_id",
            "status",
        ),
        Index(
            "ix_chunk_sets_version_status",
            "document_version_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_new_uuid,
    )
    parse_result_id: Mapped[int] = mapped_column(
        ForeignKey("parse_results.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    stored_file_id: Mapped[int] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    strategy_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    strategy_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    configuration_json: Mapped[str] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql"),
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    canonical_content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=ChunkSetStatus.PENDING.value,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    parse_result: Mapped["ParseResult"] = relationship(
        back_populates="chunk_sets"
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="chunk_set",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="KnowledgeChunk.chunk_set_id",
        order_by="KnowledgeChunk.ordinal",
    )
    executions: Mapped[list["ChunkingExecution"]] = relationship(
        back_populates="chunk_set",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChunkingExecution.attempt_number",
    )
    relationships: Mapped[list["ChunkRelationship"]] = relationship(
        back_populates="chunk_set",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChunkRelationship.id",
    )
    artifacts: Mapped[list["ChunkingArtifact"]] = relationship(
        back_populates="chunk_set",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChunkingArtifact.id",
    )


@event.listens_for(ChunkSet, "before_update")
def _protect_successful_chunk_set(mapper, connection, target) -> None:
    del mapper, connection
    state = inspect(target)
    previous_status = (
        state.attrs.status.history.deleted[0]
        if state.attrs.status.history.deleted
        else target.status
    )
    if previous_status != ChunkSetStatus.SUCCEEDED.value:
        return
    immutable_fields = (
        "parse_result_id",
        "document_version_id",
        "stored_file_id",
        "strategy_name",
        "strategy_version",
        "configuration_json",
        "configuration_hash",
        "canonical_content_hash",
        "chunk_count",
        "total_character_count",
        "total_word_count",
        "content_hash",
        "started_at",
        "completed_at",
    )
    if any(
        state.attrs[field].history.has_changes() for field in immutable_fields
    ):
        raise ValueError("Successful chunk sets are immutable")
    if (
        state.attrs.status.history.has_changes()
        and target.status != ChunkSetStatus.INVALIDATED.value
    ):
        raise ValueError("Successful chunk sets may only be invalidated")


class KnowledgeChunk(Base):
    """Legacy Pack 1 chunk plus Sprint 1G deterministic chunk fields.

    Legacy rows have ``chunk_set_id`` null. Sprint 1G rows have
    ``document_id`` null and preserve their exact text in both ``content``
    (legacy compatibility) and ``text`` (the canonical chunk API).
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        UniqueConstraint(
            "chunk_set_id",
            "ordinal",
            name="uq_knowledge_chunk_ordinal",
        ),
        UniqueConstraint(
            "chunk_set_id",
            "stable_key",
            name="uq_knowledge_chunk_stable_key",
        ),
        CheckConstraint(
            "chunk_set_id IS NULL OR ordinal >= 0",
            name="ck_knowledge_chunks_ordinal",
        ),
        Index("ix_chunks_category", "category"),
        Index(
            "ix_knowledge_chunks_set_type",
            "chunk_set_id",
            "content_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="general",
    )
    content: Mapped[str] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql"),
        nullable=False,
    )
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uuid: Mapped[str | None] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=_new_uuid,
    )
    chunk_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="CASCADE"),
        index=True,
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    stable_key: Mapped[str | None] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(50), index=True)
    text: Mapped[str | None] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql")
    )
    normalized_text: Mapped[str | None] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql")
    )
    heading_context_json: Mapped[list[Any] | dict[str, Any] | None] = (
        mapped_column(JSON)
    )
    language: Mapped[str | None] = mapped_column(String(64), index=True)
    character_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    previous_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="SET NULL"),
        index=True,
    )
    next_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    document: Mapped["KnowledgeDocument | None"] = relationship(
        back_populates="chunks",
        foreign_keys=[document_id],
    )
    chunk_set: Mapped["ChunkSet | None"] = relationship(
        back_populates="chunks",
        foreign_keys=[chunk_set_id],
    )
    previous_chunk: Mapped["KnowledgeChunk | None"] = relationship(
        remote_side=[id],
        foreign_keys=[previous_chunk_id],
        post_update=True,
    )
    next_chunk: Mapped["KnowledgeChunk | None"] = relationship(
        remote_side=[id],
        foreign_keys=[next_chunk_id],
        post_update=True,
    )
    source_spans: Mapped[list["ChunkSourceSpan"]] = relationship(
        back_populates="knowledge_chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChunkSourceSpan.source_order",
    )


def _successful_parent(connection, chunk_set_id: int | None) -> bool:
    if chunk_set_id is None:
        return False
    status = connection.scalar(
        select(ChunkSet.status).where(ChunkSet.id == chunk_set_id)
    )
    return status == ChunkSetStatus.SUCCEEDED.value


@event.listens_for(KnowledgeChunk, "before_update")
@event.listens_for(KnowledgeChunk, "before_delete")
def _protect_successful_chunk(mapper, connection, target) -> None:
    del mapper
    if _successful_parent(connection, target.chunk_set_id):
        raise ValueError("Chunks in successful chunk sets are immutable")


class ChunkSourceSpan(CreatedAtMixin, Base):
    __tablename__ = "chunk_source_spans"
    __table_args__ = (
        CheckConstraint(
            "text_start_in_chunk >= 0 AND "
            "text_end_in_chunk >= text_start_in_chunk",
            name="ck_chunk_source_spans_text_offsets",
        ),
        CheckConstraint(
            "table_row_start IS NULL OR table_row_end IS NULL OR "
            "table_row_end >= table_row_start",
            name="ck_chunk_source_spans_table_rows",
        ),
        UniqueConstraint(
            "knowledge_chunk_id",
            "source_order",
            name="uq_chunk_source_span_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_chunk_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_order: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_block_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    canonical_block_index: Mapped[int | None] = mapped_column(Integer)
    source_index: Mapped[int | None] = mapped_column(Integer, index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, index=True)
    section_path_json: Mapped[list[Any] | None] = mapped_column(JSON)
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    table_index: Mapped[int | None] = mapped_column(Integer)
    table_row_start: Mapped[int | None] = mapped_column(Integer)
    table_row_end: Mapped[int | None] = mapped_column(Integer)
    character_start: Mapped[int | None] = mapped_column(Integer)
    character_end: Mapped[int | None] = mapped_column(Integer)
    source_locator: Mapped[str | None] = mapped_column(String(1000))
    text_start_in_chunk: Mapped[int] = mapped_column(Integer, nullable=False)
    text_end_in_chunk: Mapped[int] = mapped_column(Integer, nullable=False)
    is_overlap: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    knowledge_chunk: Mapped[KnowledgeChunk] = relationship(
        back_populates="source_spans"
    )


class ChunkRelationship(CreatedAtMixin, Base):
    __tablename__ = "chunk_relationships"
    __table_args__ = (
        CheckConstraint(
            "source_chunk_id <> target_chunk_id",
            name="ck_chunk_relationship_not_self",
        ),
        UniqueConstraint(
            "source_chunk_id",
            "target_chunk_id",
            "relationship_type",
            name="uq_chunk_relationship_tuple",
        ),
        Index(
            "ix_chunk_relationships_set_type",
            "chunk_set_id",
            "relationship_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_set_id: Mapped[int] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_chunk_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_chunk_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )

    chunk_set: Mapped[ChunkSet] = relationship(
        back_populates="relationships"
    )
    source_chunk: Mapped[KnowledgeChunk] = relationship(
        foreign_keys=[source_chunk_id]
    )
    target_chunk: Mapped[KnowledgeChunk] = relationship(
        foreign_keys=[target_chunk_id]
    )


class ChunkingExecution(CreatedAtMixin, Base):
    __tablename__ = "chunking_executions"
    __table_args__ = (
        CheckConstraint(
            "attempt_number > 0",
            name="ck_chunking_executions_attempt_number",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_chunking_executions_duration",
        ),
        UniqueConstraint(
            "chunk_set_id",
            "attempt_number",
            name="uq_chunking_execution_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_set_id: Mapped[int] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=ChunkingExecutionStatus.RUNNING.value,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    node_name: Mapped[str | None] = mapped_column(String(255))

    chunk_set: Mapped[ChunkSet] = relationship(back_populates="executions")


class ChunkingArtifact(CreatedAtMixin, Base):
    __tablename__ = "chunking_artifacts"
    __table_args__ = (
        Index(
            "ix_chunking_artifacts_set_type",
            "chunk_set_id",
            "artifact_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_set_id: Mapped[int] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )
    content_text: Mapped[str | None] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql")
    )
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)

    chunk_set: Mapped[ChunkSet] = relationship(back_populates="artifacts")


__all__ = [
    "ChunkRelationship",
    "ChunkSet",
    "ChunkSourceSpan",
    "ChunkingArtifact",
    "ChunkingExecution",
    "KnowledgeChunk",
]
