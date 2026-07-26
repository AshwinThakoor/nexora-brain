from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin


class ConceptRelationship(CreatedAtMixin, Base):
    __tablename__ = "concept_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_concept_id",
            "target_concept_id",
            "relationship_type",
            name="uq_concept_relationship",
        ),
        CheckConstraint(
            "source_concept_id <> target_concept_id",
            name="ck_concept_relationship_not_self",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="ck_concept_relationship_confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)

    source_concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="outgoing_relationships",
        foreign_keys=[source_concept_id],
    )
    target_concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="incoming_relationships",
        foreign_keys=[target_concept_id],
    )

    def __repr__(self) -> str:
        return (
            f"ConceptRelationship(id={self.id!r}, "
            f"source_concept_id={self.source_concept_id!r}, "
            f"target_concept_id={self.target_concept_id!r}, "
            f"relationship_type={self.relationship_type!r})"
        )
