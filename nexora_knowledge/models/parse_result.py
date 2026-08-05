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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import LONGTEXT

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin, utc_now
from .enums import ParseExecutionStatus, ParseResultStatus


def _new_uuid() -> str:
    return str(uuid4())


class ParseResult(TimestampMixin, Base):
    """Current durable canonical output for one parser identity."""

    __tablename__ = "parse_results"
    __table_args__ = (
        UniqueConstraint(
            "stored_file_id",
            "input_sha256",
            "parser_name",
            "parser_version",
            name="uq_parse_result_identity",
        ),
        Index(
            "ix_parse_results_file_status",
            "stored_file_id",
            "status",
        ),
        Index(
            "ix_parse_results_version_status",
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
    stored_file_id: Mapped[int] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ingestion_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
        index=True,
    )
    parser_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    parser_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    input_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    canonical_schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=ParseResultStatus.PENDING.value,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )
    canonical_json: Mapped[str | None] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql")
    )
    statistics_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )
    metadata_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    stored_file: Mapped["StoredFile"] = relationship(
        back_populates="parse_results"
    )
    document_version: Mapped["DocumentVersion"] = relationship(
        back_populates="parse_results"
    )
    ingestion_job: Mapped["IngestionJob | None"] = relationship(
        back_populates="parse_results"
    )
    executions: Mapped[list["ParseExecution"]] = relationship(
        back_populates="parse_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ParseExecution.attempt_number",
    )
    artifacts: Mapped[list["ParseArtifact"]] = relationship(
        back_populates="parse_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ParseArtifact.id",
    )
    chunk_sets: Mapped[list["ChunkSet"]] = relationship(
        back_populates="parse_result",
        order_by="ChunkSet.id",
    )


@event.listens_for(ParseResult, "before_update")
def _protect_successful_parse_result(mapper, connection, target) -> None:
    del mapper, connection
    state = inspect(target)
    previous_status = (
        state.attrs.status.history.deleted[0]
        if state.attrs.status.history.deleted
        else target.status
    )
    if previous_status != ParseResultStatus.SUCCEEDED.value:
        return
    immutable_fields = (
        "stored_file_id",
        "document_version_id",
        "ingestion_job_id",
        "parser_name",
        "parser_version",
        "input_sha256",
        "canonical_schema_version",
        "content_hash",
        "canonical_json",
        "statistics_json",
        "metadata_json",
        "started_at",
        "completed_at",
    )
    if any(
        state.attrs[field].history.has_changes() for field in immutable_fields
    ):
        raise ValueError("Successful parse results are immutable")
    if (
        state.attrs.status.history.has_changes()
        and target.status != ParseResultStatus.INVALIDATED.value
    ):
        raise ValueError(
            "Successful parse results may only be invalidated"
        )


class ParseExecution(CreatedAtMixin, Base):
    """One preserved attempt to populate a ParseResult."""

    __tablename__ = "parse_executions"
    __table_args__ = (
        CheckConstraint(
            "attempt_number > 0",
            name="ck_parse_executions_attempt_number",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_parse_executions_duration",
        ),
        UniqueConstraint(
            "parse_result_id",
            "attempt_number",
            name="uq_parse_execution_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parse_result_id: Mapped[int] = mapped_column(
        ForeignKey("parse_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=ParseExecutionStatus.RUNNING.value,
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
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    node_name: Mapped[str | None] = mapped_column(String(255))

    parse_result: Mapped[ParseResult] = relationship(
        back_populates="executions"
    )


class ParseArtifact(CreatedAtMixin, Base):
    """Structured non-binary metadata emitted by a parser."""

    __tablename__ = "parse_artifacts"
    __table_args__ = (
        Index(
            "ix_parse_artifacts_result_type",
            "parse_result_id",
            "artifact_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parse_result_id: Mapped[int] = mapped_column(
        ForeignKey("parse_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    content_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON
    )
    content_text: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)

    parse_result: Mapped[ParseResult] = relationship(
        back_populates="artifacts"
    )


__all__ = ["ParseArtifact", "ParseExecution", "ParseResult"]
