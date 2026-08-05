from datetime import datetime
from typing import ClassVar

from .common import (
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    TypeString,
    UnitScore,
)


class EvidenceCreate(ORMResponse):
    claim_id: PositiveId
    source_id: PositiveId | None = None
    evidence_type: TypeString
    strength: UnitScore
    notes: str | None = None
    citation: str | None = None


class EvidenceUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"claim_id", "evidence_type", "strength"}
    )

    claim_id: PositiveId | None = None
    source_id: PositiveId | None = None
    evidence_type: TypeString | None = None
    strength: UnitScore | None = None
    notes: str | None = None
    citation: str | None = None


class EvidenceResponse(ORMResponse):
    id: int
    claim_id: int
    source_id: int | None
    evidence_type: str
    strength: float
    notes: str | None
    citation: str | None
    created_at: datetime
