from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import TimestampMixin


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="ck_claims_confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
    )

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="claims",
    )
    evidence_records: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="claim",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Claim(id={self.id!r}, concept_id={self.concept_id!r}, "
            f"claim_type={self.claim_type!r})"
        )
