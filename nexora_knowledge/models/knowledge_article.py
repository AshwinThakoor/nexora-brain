from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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
from .common import CreatedAtMixin, TimestampMixin
from .enums import (
    DifficultyLevel,
    KnowledgeLifecycleStatus,
    KnowledgeSectionType,
    ReviewStatus,
)


class KnowledgeArticle(TimestampMixin, Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="ck_knowledge_articles_confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    subtitle: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[str | None] = mapped_column(Text)
    detailed_explanation: Mapped[str | None] = mapped_column(Text)
    historical_background: Mapped[str | None] = mapped_column(Text)
    market_context: Mapped[str | None] = mapped_column(Text)
    trading_applications: Mapped[str | None] = mapped_column(Text)
    risk_considerations: Mapped[str | None] = mapped_column(Text)
    advantages: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    common_mistakes: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[str | None] = mapped_column(Text)
    counter_examples: Mapped[str | None] = mapped_column(Text)
    practical_checklist: Mapped[str | None] = mapped_column(Text)
    difficulty_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DifficultyLevel.BEGINNER.value,
    )
    audience_level: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en",
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=KnowledgeLifecycleStatus.DRAFT.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReviewStatus.PENDING.value,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    confidence_method: Mapped[str | None] = mapped_column(String(255))
    confidence_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    concept: Mapped["Concept | None"] = relationship(
        "Concept",
        back_populates="articles",
    )
    sections: Mapped[list["KnowledgeSection"]] = relationship(
        "KnowledgeSection",
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="KnowledgeSection.position",
    )
    faqs: Mapped[list["FAQ"]] = relationship(
        "FAQ",
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="FAQ.position",
    )
    lessons: Mapped[list["Lesson"]] = relationship(
        "Lesson",
        back_populates="knowledge_article",
        passive_deletes=True,
    )


class KnowledgeSection(TimestampMixin, Base):
    __tablename__ = "knowledge_sections"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "position",
            name="uq_knowledge_section_position",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_knowledge_sections_position_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=KnowledgeSectionType.OTHER.value,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)

    article: Mapped[KnowledgeArticle] = relationship(
        "KnowledgeArticle",
        back_populates="sections",
    )


class ConceptAlias(CreatedAtMixin, Base):
    __tablename__ = "concept_aliases"
    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "normalized_alias",
            "language",
            name="uq_concept_alias_normalized_language",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    alias_type: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en",
    )
    is_preferred: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="aliases",
    )


class FAQ(TimestampMixin, Base):
    __tablename__ = "faqs"
    __table_args__ = (
        UniqueConstraint("article_id", "position", name="uq_faq_position"),
        CheckConstraint("position >= 0", name="ck_faqs_position_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DifficultyLevel.BEGINNER.value,
    )

    article: Mapped[KnowledgeArticle] = relationship(
        "KnowledgeArticle",
        back_populates="faqs",
    )
