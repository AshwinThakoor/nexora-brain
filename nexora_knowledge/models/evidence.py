from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin


class Evidence(CreatedAtMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "strength >= 0.0 AND strength <= 1.0",
            name="ck_evidence_strength_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    citation: Mapped[str | None] = mapped_column(Text)

    claim: Mapped["Claim"] = relationship(
        "Claim",
        back_populates="evidence_records",
    )
    source: Mapped["Source | None"] = relationship(
        "Source",
        back_populates="evidence_records",
    )

    def __repr__(self) -> str:
        return (
            f"Evidence(id={self.id!r}, claim_id={self.claim_id!r}, "
            f"evidence_type={self.evidence_type!r})"
        )
