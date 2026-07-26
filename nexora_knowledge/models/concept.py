from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import TimestampMixin
from .tag import concept_tags


class Concept(TimestampMixin, Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="beginner",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="concepts",
    )
    claims: Mapped[list["Claim"]] = relationship(
        "Claim",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    outgoing_relationships: Mapped[list["ConceptRelationship"]] = relationship(
        "ConceptRelationship",
        back_populates="source_concept",
        cascade="all, delete-orphan",
        foreign_keys="ConceptRelationship.source_concept_id",
    )
    incoming_relationships: Mapped[list["ConceptRelationship"]] = relationship(
        "ConceptRelationship",
        back_populates="target_concept",
        cascade="all, delete-orphan",
        foreign_keys="ConceptRelationship.target_concept_id",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary=concept_tags,
        back_populates="concepts",
    )

    def __repr__(self) -> str:
        return f"Concept(id={self.id!r}, title={self.title!r}, slug={self.slug!r})"
