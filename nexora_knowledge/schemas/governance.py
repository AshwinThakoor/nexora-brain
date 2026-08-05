from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from pydantic import Field, model_validator

from ..models.enums import ReviewStatus
from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    RequiredText,
    StatusString,
    TypeString,
    UnitScore,
)


class KnowledgeReviewBase(ORMResponse):
    entity_type: TypeString
    entity_id: PositiveId
    reviewer: NameString | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    decision: NameString | None = None
    notes: str | None = None
    reviewed_at: datetime | None = None
    next_review_at: datetime | None = None


class KnowledgeReviewCreate(KnowledgeReviewBase):
    pass


class KnowledgeReviewUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"entity_type", "entity_id", "review_status"}
    )

    entity_type: TypeString | None = None
    entity_id: PositiveId | None = None
    reviewer: NameString | None = None
    review_status: ReviewStatus | None = None
    decision: NameString | None = None
    notes: str | None = None
    reviewed_at: datetime | None = None
    next_review_at: datetime | None = None


class KnowledgeReviewRead(KnowledgeReviewBase):
    id: int
    created_at: datetime


class KnowledgeRevisionBase(ORMResponse):
    entity_type: TypeString
    entity_id: PositiveId
    version_number: int = Field(ge=1)
    change_type: TypeString
    change_summary: RequiredText
    snapshot_json: dict[str, Any] | list[Any]
    created_by: NameString | None = None


class KnowledgeRevisionCreate(KnowledgeRevisionBase):
    pass


class KnowledgeRevisionUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "entity_type",
            "entity_id",
            "version_number",
            "change_type",
            "change_summary",
            "snapshot_json",
        }
    )

    entity_type: TypeString | None = None
    entity_id: PositiveId | None = None
    version_number: int | None = Field(default=None, ge=1)
    change_type: TypeString | None = None
    change_summary: RequiredText | None = None
    snapshot_json: dict[str, Any] | list[Any] | None = None
    created_by: NameString | None = None


class KnowledgeRevisionRead(KnowledgeRevisionBase):
    id: int
    created_at: datetime


class ClaimConflictBase(ORMResponse):
    claim_a_id: PositiveId
    claim_b_id: PositiveId
    conflict_type: TypeString
    description: RequiredText
    status: StatusString = "open"
    resolution: str | None = None
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def claims_must_differ(self):
        if self.claim_a_id == self.claim_b_id:
            raise ValueError("A claim cannot conflict with itself")
        return self


class ClaimConflictCreate(ClaimConflictBase):
    pass


class ClaimConflictUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "claim_a_id",
            "claim_b_id",
            "conflict_type",
            "description",
            "status",
        }
    )

    claim_a_id: PositiveId | None = None
    claim_b_id: PositiveId | None = None
    conflict_type: TypeString | None = None
    description: RequiredText | None = None
    status: StatusString | None = None
    resolution: str | None = None
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def supplied_claims_must_differ(self):
        if (
            self.claim_a_id is not None
            and self.claim_b_id is not None
            and self.claim_a_id == self.claim_b_id
        ):
            raise ValueError("A claim cannot conflict with itself")
        return self


class ClaimConflictRead(ClaimConflictBase):
    id: int
    created_at: datetime


class SourceAssessmentBase(ORMResponse):
    source_id: PositiveId
    authority_score: UnitScore | None = None
    accuracy_score: UnitScore | None = None
    recency_score: UnitScore | None = None
    transparency_score: UnitScore | None = None
    relevance_score: UnitScore | None = None
    overall_score: UnitScore | None = None
    assessment_method: NameString | None = None
    notes: str | None = None
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class SourceAssessmentCreate(SourceAssessmentBase):
    pass


class SourceAssessmentUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"source_id", "assessed_at"}
    )

    source_id: PositiveId | None = None
    authority_score: UnitScore | None = None
    accuracy_score: UnitScore | None = None
    recency_score: UnitScore | None = None
    transparency_score: UnitScore | None = None
    relevance_score: UnitScore | None = None
    overall_score: UnitScore | None = None
    assessment_method: NameString | None = None
    notes: str | None = None
    assessed_at: datetime | None = None


class SourceAssessmentRead(SourceAssessmentBase):
    id: int
    created_at: datetime


KnowledgeReviewResponse = KnowledgeReviewRead
KnowledgeRevisionResponse = KnowledgeRevisionRead
ClaimConflictResponse = ClaimConflictRead
SourceAssessmentResponse = SourceAssessmentRead


__all__ = [
    name
    for name, value in globals().items()
    if (
        isinstance(value, type)
        and value.__module__ == __name__
        and name.endswith(("Base", "Create", "Update", "Read", "Response"))
    )
]
