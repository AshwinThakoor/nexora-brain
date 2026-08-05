from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin


concept_tags = Table(
    "concept_tags",
    Base.metadata,
    Column("concept_id", ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
    UniqueConstraint("concept_id", "tag_id", name="uq_concept_tag"),
)


class Tag(CreatedAtMixin, Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    concepts: Mapped[list["Concept"]] = relationship(
        "Concept",
        secondary=concept_tags,
        back_populates="tags",
    )
    sources: Mapped[list["Source"]] = relationship(
        "Source",
        secondary="source_tags",
        back_populates="tags",
        order_by="Source.title",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        secondary="document_tags",
        back_populates="tags",
        order_by="Document.title",
    )

    def __repr__(self) -> str:
        return f"Tag(id={self.id!r}, name={self.name!r}, slug={self.slug!r})"
