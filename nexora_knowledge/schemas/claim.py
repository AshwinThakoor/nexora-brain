from datetime import datetime
from typing import ClassVar

from pydantic import Field

from ..models.enums import KnowledgeLifecycleStatus
from .common import (
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    RequiredText,
    StatusString,
    TypeString,
    UnitScore,
)
from .evidence import EvidenceResponse


class ClaimCreate(ORMResponse):
    concept_id: PositiveId
    statement: RequiredText
    claim_type: TypeString = "general"
    confidence_score: UnitScore | None = None
    status: StatusString = "draft"
    lifecycle_status: KnowledgeLifecycleStatus = KnowledgeLifecycleStatus.DRAFT
    confidence_method: str | None = None
    confidence_reason: str | None = None
    last_reviewed_at: datetime | None = None


class ClaimUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "concept_id",
            "statement",
            "claim_type",
            "status",
            "lifecycle_status",
        }
    )

    concept_id: PositiveId | None = None
    statement: RequiredText | None = None
    claim_type: TypeString | None = None
    confidence_score: UnitScore | None = None
    status: StatusString | None = None
    lifecycle_status: KnowledgeLifecycleStatus | None = None
    confidence_method: str | None = None
    confidence_reason: str | None = None
    last_reviewed_at: datetime | None = None


class ClaimResponse(ORMResponse):
    id: int
    concept_id: int
    statement: str
    claim_type: str
    confidence_score: float | None
    status: str
    lifecycle_status: str
    confidence_method: str | None
    confidence_reason: str | None
    last_reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClaimDetail(ClaimResponse):
    evidence_records: list[EvidenceResponse] = Field(default_factory=list)
