from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar

from pydantic import Field, StringConstraints

from ..models.enums import (
    DifficultyLevel,
    KnowledgeLifecycleStatus,
    KnowledgeSectionType,
    ReviewStatus,
)
from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    RequiredText,
    SlugString,
    TitleString,
    TypeString,
    UnitScore,
)


LanguageString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
]


class KnowledgeSectionBase(ORMResponse):
    article_id: PositiveId
    section_type: KnowledgeSectionType = KnowledgeSectionType.OTHER
    title: TitleString
    content: RequiredText
    position: int = Field(ge=0)
    metadata_json: dict[str, Any] | list[Any] | None = None


class KnowledgeSectionCreate(KnowledgeSectionBase):
    pass


class KnowledgeSectionUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"article_id", "section_type", "title", "content", "position"}
    )

    article_id: PositiveId | None = None
    section_type: KnowledgeSectionType | None = None
    title: TitleString | None = None
    content: RequiredText | None = None
    position: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, Any] | list[Any] | None = None


class KnowledgeSectionRead(KnowledgeSectionBase):
    id: int
    created_at: datetime
    updated_at: datetime


class FAQBase(ORMResponse):
    article_id: PositiveId
    question: RequiredText
    answer: RequiredText
    position: int = Field(ge=0)
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER


class FAQCreate(FAQBase):
    pass


class FAQUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "article_id",
            "question",
            "answer",
            "position",
            "difficulty_level",
        }
    )

    article_id: PositiveId | None = None
    question: RequiredText | None = None
    answer: RequiredText | None = None
    position: int | None = Field(default=None, ge=0)
    difficulty_level: DifficultyLevel | None = None


class FAQRead(FAQBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ConceptAliasBase(ORMResponse):
    concept_id: PositiveId
    alias: TitleString
    alias_type: TypeString | None = None
    language: LanguageString = "en"
    is_preferred: bool = False


class ConceptAliasCreate(ConceptAliasBase):
    pass


class ConceptAliasUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"concept_id", "alias", "language", "is_preferred"}
    )

    concept_id: PositiveId | None = None
    alias: TitleString | None = None
    alias_type: TypeString | None = None
    language: LanguageString | None = None
    is_preferred: bool | None = None


class ConceptAliasRead(ConceptAliasBase):
    id: int
    normalized_alias: str
    created_at: datetime


class KnowledgeArticleBase(ORMResponse):
    concept_id: PositiveId | None = None
    title: TitleString
    slug: SlugString
    subtitle: TitleString | None = None
    summary: str | None = None
    definition: str | None = None
    detailed_explanation: str | None = None
    historical_background: str | None = None
    market_context: str | None = None
    trading_applications: str | None = None
    risk_considerations: str | None = None
    advantages: str | None = None
    limitations: str | None = None
    common_mistakes: str | None = None
    examples: str | None = None
    counter_examples: str | None = None
    practical_checklist: str | None = None
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER
    audience_level: TypeString | None = None
    language: LanguageString = "en"
    lifecycle_status: KnowledgeLifecycleStatus = KnowledgeLifecycleStatus.DRAFT
    review_status: ReviewStatus = ReviewStatus.PENDING
    confidence_score: UnitScore | None = None
    confidence_method: NameString | None = None
    confidence_reason: str | None = None
    version: int = Field(default=1, ge=1)
    published_at: datetime | None = None
    last_reviewed_at: datetime | None = None


class KnowledgeArticleCreate(KnowledgeArticleBase):
    pass


class KnowledgeArticleUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "title",
            "slug",
            "difficulty_level",
            "language",
            "lifecycle_status",
            "review_status",
            "version",
        }
    )

    concept_id: PositiveId | None = None
    title: TitleString | None = None
    slug: SlugString | None = None
    subtitle: TitleString | None = None
    summary: str | None = None
    definition: str | None = None
    detailed_explanation: str | None = None
    historical_background: str | None = None
    market_context: str | None = None
    trading_applications: str | None = None
    risk_considerations: str | None = None
    advantages: str | None = None
    limitations: str | None = None
    common_mistakes: str | None = None
    examples: str | None = None
    counter_examples: str | None = None
    practical_checklist: str | None = None
    difficulty_level: DifficultyLevel | None = None
    audience_level: TypeString | None = None
    language: LanguageString | None = None
    lifecycle_status: KnowledgeLifecycleStatus | None = None
    review_status: ReviewStatus | None = None
    confidence_score: UnitScore | None = None
    confidence_method: NameString | None = None
    confidence_reason: str | None = None
    version: int | None = Field(default=None, ge=1)
    published_at: datetime | None = None
    last_reviewed_at: datetime | None = None


class KnowledgeArticleRead(KnowledgeArticleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    sections: list[KnowledgeSectionRead] = Field(default_factory=list)
    faqs: list[FAQRead] = Field(default_factory=list)


KnowledgeSectionResponse = KnowledgeSectionRead
FAQResponse = FAQRead
ConceptAliasResponse = ConceptAliasRead
KnowledgeArticleResponse = KnowledgeArticleRead


__all__ = [
    "ConceptAliasBase",
    "ConceptAliasCreate",
    "ConceptAliasRead",
    "ConceptAliasResponse",
    "ConceptAliasUpdate",
    "FAQBase",
    "FAQCreate",
    "FAQRead",
    "FAQResponse",
    "FAQUpdate",
    "KnowledgeArticleBase",
    "KnowledgeArticleCreate",
    "KnowledgeArticleRead",
    "KnowledgeArticleResponse",
    "KnowledgeArticleUpdate",
    "KnowledgeSectionBase",
    "KnowledgeSectionCreate",
    "KnowledgeSectionRead",
    "KnowledgeSectionResponse",
    "KnowledgeSectionUpdate",
]
