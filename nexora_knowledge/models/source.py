from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import TimestampMixin


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
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    publisher: Mapped[str | None] = mapped_column(String(255))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(String(2048))
    license: Mapped[str | None] = mapped_column(String(255))
    quality_score: Mapped[float | None] = mapped_column(Float)
    trust_score: Mapped[float | None] = mapped_column(Float)

    evidence_records: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="source",
    )

    def __repr__(self) -> str:
        return f"Source(id={self.id!r}, title={self.title!r}, source_type={self.source_type!r})"
