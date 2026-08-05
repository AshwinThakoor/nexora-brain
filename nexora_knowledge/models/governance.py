from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin, utc_now
from .enums import ReviewStatus


SCORE_FIELDS = (
    "authority_score",
    "accuracy_score",
    "recency_score",
    "transparency_score",
    "relevance_score",
    "overall_score",
)


class KnowledgeReview(CreatedAtMixin, Base):
    __tablename__ = "knowledge_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reviewer: Mapped[str | None] = mapped_column(String(255))
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReviewStatus.PENDING.value,
    )
    decision: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeRevision(CreatedAtMixin, Base):
    __tablename__ = "knowledge_revisions"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "version_number",
            name="uq_knowledge_revision_entity_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(String(255))


class ClaimConflict(CreatedAtMixin, Base):
    __tablename__ = "claim_conflicts"
    __table_args__ = (
        CheckConstraint(
            "claim_a_id <> claim_b_id",
            name="ck_claim_conflicts_not_self",
        ),
        CheckConstraint(
            "claim_a_id < claim_b_id",
            name="ck_claim_conflicts_canonical_pair",
        ),
        UniqueConstraint(
            "claim_a_id",
            "claim_b_id",
            name="uq_claim_conflict_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_a_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_b_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conflict_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="open",
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    claim_a: Mapped["Claim"] = relationship(
        "Claim",
        back_populates="conflicts_as_a",
        foreign_keys=[claim_a_id],
    )
    claim_b: Mapped["Claim"] = relationship(
        "Claim",
        back_populates="conflicts_as_b",
        foreign_keys=[claim_b_id],
    )


class SourceAssessment(CreatedAtMixin, Base):
    __tablename__ = "source_assessments"
    __table_args__ = tuple(
        CheckConstraint(
            f"{field} IS NULL OR ({field} >= 0.0 AND {field} <= 1.0)",
            name=f"ck_source_assessments_{field}_range",
        )
        for field in SCORE_FIELDS
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    authority_score: Mapped[float | None] = mapped_column(Float)
    accuracy_score: Mapped[float | None] = mapped_column(Float)
    recency_score: Mapped[float | None] = mapped_column(Float)
    transparency_score: Mapped[float | None] = mapped_column(Float)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    assessment_method: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="assessments",
    )
