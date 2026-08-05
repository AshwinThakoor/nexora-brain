from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin, utc_now
from .enums import (
    DocumentStatus,
    DocumentType,
    ProcessingStatus,
    RelationshipType,
)


def _new_uuid() -> str:
    return str(uuid4())


class CurrentVersionFlag(TypeDecorator[bool]):
    """Store false as NULL so a portable unique constraint permits many old versions."""

    impl = Boolean
    cache_ok = True

    def process_bind_param(self, value: bool | None, dialect) -> bool | None:
        del dialect
        return True if value else None

    def process_result_value(self, value: bool | None, dialect) -> bool:
        del dialect
        return bool(value)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    publisher: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    license_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN")
    license_notes: Mapped[str | None] = mapped_column(Text)
    commercial_use_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index"
    )


class Document(TimestampMixin, Base):
    """Registry metadata for a logical document that has not been parsed."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "NOT (active = 1 AND archived = 1)",
            name="ck_documents_lifecycle",
        ),
        CheckConstraint(
            "publication_year IS NULL OR "
            "(publication_year >= 1000 AND publication_year <= 9999)",
            name="ck_documents_publication_year",
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
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    abstract: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=DocumentType.OTHER.value,
    )
    language: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        default="en",
    )
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, index=True)
    author_override: Mapped[str | None] = mapped_column(String(255), index=True)
    publisher_override: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=DocumentStatus.REGISTERED.value,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    source: Mapped["Source"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentVersion.id",
    )
    files: Mapped[list["DocumentFile"]] = relationship(
        "DocumentFile",
        secondary="document_versions",
        primaryjoin="Document.id == DocumentVersion.document_id",
        secondaryjoin=(
            "DocumentVersion.id == DocumentFile.document_version_id"
        ),
        viewonly=True,
        order_by="DocumentFile.id",
    )
    identifiers: Mapped[list["DocumentIdentifier"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentIdentifier.id",
    )
    relationships: Mapped[list["DocumentRelationship"]] = relationship(
        foreign_keys="DocumentRelationship.source_document_id",
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentRelationship.id",
    )
    incoming_relationships: Mapped[list["DocumentRelationship"]] = relationship(
        foreign_keys="DocumentRelationship.target_document_id",
        back_populates="target_document",
        passive_deletes=True,
        order_by="DocumentRelationship.id",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="document_tags",
        back_populates="documents",
        order_by="Tag.name",
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="document",
        order_by="IngestionJob.id",
    )
    stored_files: Mapped[list["StoredFile"]] = relationship(
        "StoredFile",
        secondary="document_versions",
        primaryjoin="Document.id == DocumentVersion.document_id",
        secondaryjoin=(
            "DocumentVersion.id == StoredFile.document_version_id"
        ),
        viewonly=True,
        order_by="StoredFile.id",
    )
    @property
    def current_version(self) -> DocumentVersion | None:
        return next((item for item in self.versions if item.is_current), None)

    def __repr__(self) -> str:
        return (
            f"Document(id={self.id!r}, slug={self.slug!r}, "
            f"title={self.title!r})"
        )


class DocumentVersion(CreatedAtMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version",
            name="uq_document_version",
        ),
        UniqueConstraint(
            "document_id",
            "checksum",
            name="uq_document_version_checksum",
        ),
        UniqueConstraint(
            "document_id",
            "is_current",
            name="uq_document_current_version",
        ),
        CheckConstraint(
            "is_current IS NULL OR is_current = 1",
            name="ck_document_versions_current",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date)
    # False is persisted as NULL by CurrentVersionFlag. Both supported databases
    # allow multiple NULL values while the composite unique constraint permits
    # no more than one true row for each document.
    is_current: Mapped[bool] = mapped_column(
        CurrentVersionFlag(),
        nullable=True,
        default=False,
    )

    document: Mapped[Document] = relationship(back_populates="versions")
    files: Mapped[list["DocumentFile"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentFile.id",
    )
    stored_files: Mapped[list["StoredFile"]] = relationship(
        "StoredFile",
        back_populates="document_version",
        order_by="StoredFile.id",
    )
    parse_results: Mapped[list["ParseResult"]] = relationship(
        "ParseResult",
        back_populates="document_version",
        order_by="ParseResult.id",
    )


@event.listens_for(DocumentVersion, "before_update")
def _protect_immutable_version_fields(mapper, connection, target) -> None:
    """Allow current-version rotation while protecting version metadata."""

    del mapper, connection
    state = inspect(target)
    immutable_fields = (
        "document_id",
        "version",
        "checksum",
        "change_summary",
        "release_date",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("Document versions are immutable")


class DocumentFile(CreatedAtMixin, Base):
    """Metadata for a physical file; bytes are managed by a future sprint."""

    __tablename__ = "document_files"
    __table_args__ = (
        CheckConstraint(
            "size_bytes >= 0",
            name="ck_document_files_size_bytes",
        ),
        CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_document_files_page_count",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=ProcessingStatus.PENDING.value,
    )

    document_version: Mapped[DocumentVersion] = relationship(
        back_populates="files"
    )


class DocumentIdentifier(Base):
    __tablename__ = "document_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "identifier_type",
            "identifier_value",
            name="uq_document_identifier",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identifier_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    identifier_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    document: Mapped[Document] = relationship(back_populates="identifiers")


class DocumentRelationship(CreatedAtMixin, Base):
    __tablename__ = "document_relationships"
    __table_args__ = (
        CheckConstraint(
            "source_document_id <> target_document_id",
            name="ck_document_relationship_distinct",
        ),
        UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationship",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=RelationshipType.REFERENCES.value,
    )

    source_document: Mapped[Document] = relationship(
        foreign_keys=[source_document_id],
        back_populates="relationships",
    )
    target_document: Mapped[Document] = relationship(
        foreign_keys=[target_document_id],
        back_populates="incoming_relationships",
    )


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ImportBatch(CreatedAtMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_new_uuid,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=ProcessingStatus.PENDING.value,
    )
    created_by: Mapped[str | None] = mapped_column(String(255), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


__all__ = [
    "CurrentVersionFlag",
    "Document",
    "DocumentFile",
    "DocumentIdentifier",
    "DocumentRelationship",
    "DocumentTag",
    "DocumentVersion",
    "ImportBatch",
    "KnowledgeDocument",
]
