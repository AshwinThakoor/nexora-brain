from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin
from .enums import StorageProviderType, UploadStatus


def _new_uuid() -> str:
    return str(uuid4())


class StorageProvider(CreatedAtMixin, Base):
    """Database inventory for configured provider identities."""

    __tablename__ = "storage_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        default=True,
    )


class UploadSession(CreatedAtMixin, Base):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_upload_sessions_expiry",
        ),
        CheckConstraint(
            "NOT (completed_at IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_upload_sessions_terminal_state",
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
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=UploadStatus.CREATED.value,
    )
    created_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    stored_file: Mapped["StoredFile | None"] = relationship(
        back_populates="upload_session",
        uselist=False,
    )


class StoredFile(CreatedAtMixin, Base):
    __tablename__ = "stored_files"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0",
            name="ck_stored_files_size",
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
    upload_session_id: Mapped[int] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    normalized_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    sha1: Mapped[str | None] = mapped_column(String(40))
    md5: Mapped[str | None] = mapped_column(String(32))

    upload_session: Mapped[UploadSession] = relationship(
        back_populates="stored_file"
    )
    document_version: Mapped["DocumentVersion"] = relationship(
        back_populates="stored_files"
    )
    hashes: Mapped[list["FileHash"]] = relationship(
        back_populates="stored_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FileHash.algorithm",
    )
    parse_results: Mapped[list["ParseResult"]] = relationship(
        "ParseResult",
        back_populates="stored_file",
        order_by="ParseResult.id",
    )


class FileHash(Base):
    __tablename__ = "file_hashes"
    __table_args__ = (
        UniqueConstraint(
            "stored_file_id",
            "algorithm",
            name="uq_file_hash_algorithm",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stored_file_id: Mapped[int] = mapped_column(
        ForeignKey("stored_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    algorithm: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(128), nullable=False)

    stored_file: Mapped[StoredFile] = relationship(back_populates="hashes")


__all__ = [
    "FileHash",
    "StorageProvider",
    "StoredFile",
    "UploadSession",
]
