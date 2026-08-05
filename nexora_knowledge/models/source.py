from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import TimestampMixin
from .enums import TrustLevel


def _new_uuid() -> str:
    return str(uuid4())


def _new_source_slug() -> str:
    """Supply a collision-resistant slug for legacy source constructors."""
    return f"source-{uuid4().hex}"


class SourceOrganization(Base):
    __tablename__ = "source_organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    website: Mapped[str | None] = mapped_column(String(2048))
    country: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    sources: Mapped[list[Source]] = relationship(
        back_populates="organization",
    )


class SourceLicense(Base):
    __tablename__ = "source_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(String(2048))
    allows_ingestion: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    allows_distribution: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    sources: Mapped[list[Source]] = relationship(
        back_populates="license_record",
    )


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 1.0)",
            name="ck_sources_quality_score_range",
        ),
        CheckConstraint(
            "trust_score IS NULL OR (trust_score >= 0.0 AND trust_score <= 1.0)",
            name="ck_sources_trust_score_range",
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
        default=_new_source_slug,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="en",
    )
    trust_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TrustLevel.MEDIUM.value,
    )
    publication_date: Mapped[date | None] = mapped_column(Date)
    publisher: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    isbn: Mapped[str | None] = mapped_column(
        String(32),
        unique=True,
        index=True,
    )
    doi: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(String(2048))
    external_identifier: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_organizations.id", ondelete="SET NULL"),
        index=True,
    )
    license_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_licenses.id", ondelete="SET NULL"),
        index=True,
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

    # Pack 2B compatibility fields. The Pack 3 registry uses publication_date,
    # trust_level, and license_id while existing graph callers keep working.
    publication_year: Mapped[int | None] = mapped_column(Integer)
    license: Mapped[str | None] = mapped_column(String(255))
    quality_score: Mapped[float | None] = mapped_column(Float)
    trust_score: Mapped[float | None] = mapped_column(Float)

    organization: Mapped[SourceOrganization | None] = relationship(
        back_populates="sources",
    )
    license_record: Mapped[SourceLicense | None] = relationship(
        back_populates="sources",
    )
    aliases: Mapped[list[SourceAlias]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SourceAlias.id",
    )
    versions: Mapped[list[SourceVersion]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SourceVersion.id",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="source_tags",
        back_populates="sources",
        order_by="Tag.name",
    )
    evidence_records: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="source",
    )
    assessments: Mapped[list["SourceAssessment"]] = relationship(
        "SourceAssessment",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="SourceAssessment.assessed_at",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="source",
        order_by="Document.id",
    )

    @property
    def source_assessments(self) -> list["SourceAssessment"]:
        """Descriptive compatibility alias for assessment records."""
        return self.assessments

    def __repr__(self) -> str:
        return (
            f"Source(id={self.id!r}, slug={self.slug!r}, "
            f"title={self.title!r}, source_type={self.source_type!r})"
        )


class SourceAlias(Base):
    __tablename__ = "source_aliases"
    __table_args__ = (
        UniqueConstraint("source_id", "alias", name="uq_source_alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(500), nullable=False)

    source: Mapped[Source] = relationship(back_populates="aliases")


class SourceVersion(Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "version",
            name="uq_source_version",
        ),
        UniqueConstraint(
            "source_id",
            "checksum",
            name="uq_source_version_checksum",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship(back_populates="versions")


class SourceTag(Base):
    __tablename__ = "source_tags"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


__all__ = [
    "Source",
    "SourceAlias",
    "SourceLicense",
    "SourceOrganization",
    "SourceTag",
    "SourceVersion",
]
