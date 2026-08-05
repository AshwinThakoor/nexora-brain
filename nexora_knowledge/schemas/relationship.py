from datetime import datetime
from typing import ClassVar

from pydantic import model_validator

from .common import (
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    TypeString,
    UnitScore,
)


class RelationshipCreate(ORMResponse):
    source_concept_id: PositiveId
    target_concept_id: PositiveId
    relationship_type: TypeString
    description: str | None = None
    confidence_score: UnitScore | None = None

    @model_validator(mode="after")
    def reject_self_reference(self):
        if self.source_concept_id == self.target_concept_id:
            raise ValueError("Source and target concepts must be different")
        return self


class RelationshipUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"source_concept_id", "target_concept_id", "relationship_type"}
    )

    source_concept_id: PositiveId | None = None
    target_concept_id: PositiveId | None = None
    relationship_type: TypeString | None = None
    description: str | None = None
    confidence_score: UnitScore | None = None

    @model_validator(mode="after")
    def reject_complete_self_reference(self):
        if (
            self.source_concept_id is not None
            and self.target_concept_id is not None
            and self.source_concept_id == self.target_concept_id
        ):
            raise ValueError("Source and target concepts must be different")
        return self


class RelationshipResponse(ORMResponse):
    id: int
    source_concept_id: int
    target_concept_id: int
    relationship_type: str
    description: str | None
    confidence_score: float | None
    created_at: datetime
