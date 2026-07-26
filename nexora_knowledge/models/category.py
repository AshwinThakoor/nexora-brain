from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import TimestampMixin


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent: Mapped[Category | None] = relationship(
        "Category",
        back_populates="children",
        foreign_keys=[parent_id],
        remote_side="Category.id",
    )
    children: Mapped[list[Category]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys=[parent_id],
    )
    concepts: Mapped[list["Concept"]] = relationship(
        "Concept",
        back_populates="category",
    )

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, name={self.name!r}, slug={self.slug!r})"
