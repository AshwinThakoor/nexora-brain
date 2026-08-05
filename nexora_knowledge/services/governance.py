from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    AssetClass,
    CaseStudy,
    Claim,
    ClaimConflict,
    Concept,
    EconomicEventType,
    Formula,
    Indicator,
    Instrument,
    KnowledgeArticle,
    KnowledgeReview,
    KnowledgeRevision,
    Pattern,
    Source,
    SourceAssessment,
    Strategy,
)
from ..models.governance import SCORE_FIELDS
from ..models.enums import ReviewStatus
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


ModelT = TypeVar("ModelT")

GOVERNABLE_MODELS = (
    Concept,
    Claim,
    Source,
    KnowledgeArticle,
    AssetClass,
    Instrument,
    Indicator,
    Strategy,
    Pattern,
    EconomicEventType,
    Formula,
    CaseStudy,
)


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).casefold()


ENTITY_MODELS: dict[str, type] = {}
for _model in GOVERNABLE_MODELS:
    _table_name = _model.__tablename__.casefold()
    _singular_table_name = (
        f"{_table_name[:-3]}y"
        if _table_name.endswith("ies")
        else _table_name.removesuffix("s")
    )
    for _key in (
        _model.__name__.casefold(),
        _snake_case(_model.__name__),
        _table_name,
        _singular_table_name,
    ):
        ENTITY_MODELS[_key] = _model


def _normalize_entity_type(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _validate_entity(db: Session, entity_type: str, entity_id: int) -> str:
    normalized_type = _normalize_entity_type(entity_type)
    model = ENTITY_MODELS.get(normalized_type)
    if model is None:
        raise ResourceValidationError(
            f"Unsupported governable entity_type: {entity_type}"
        )
    if db.get(model, entity_id) is None:
        raise ResourceNotFoundError(model.__name__, entity_id)
    return normalized_type


def _save(db: Session, *, message: str, commit: bool) -> None:
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(message) from exc


def _validate_review_status(value: Any) -> None:
    if value is None:
        return
    normalized = getattr(value, "value", value)
    if normalized not in {item.value for item in ReviewStatus}:
        raise ResourceValidationError("review_status is invalid")


def _get(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise ResourceNotFoundError(model.__name__, item_id)
    return item


def _update(
    db: Session,
    model: type[ModelT],
    item_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool,
) -> ModelT:
    item = _get(db, model, item_id)
    for field, value in dict(values).items():
        setattr(item, field, value)
    _save(
        db,
        message=f"{model.__name__} could not be updated",
        commit=commit,
    )
    return item


def _delete(
    db: Session,
    model: type[ModelT],
    item_id: int,
    *,
    commit: bool,
) -> None:
    db.delete(_get(db, model, item_id))
    _save(
        db,
        message=f"{model.__name__} could not be deleted",
        commit=commit,
    )


def create_knowledge_review(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> KnowledgeReview:
    data = dict(values)
    data["entity_type"] = _validate_entity(
        db,
        data["entity_type"],
        data["entity_id"],
    )
    _validate_review_status(data.get("review_status"))
    review = KnowledgeReview(**data)
    db.add(review)
    _save(
        db,
        message="KnowledgeReview could not be created",
        commit=commit,
    )
    return review


def get_knowledge_review(db, item_id):
    return _get(db, KnowledgeReview, item_id)


def update_knowledge_review(db, item_id, values, *, commit=True):
    data = dict(values)
    current = get_knowledge_review(db, item_id)
    if "entity_type" in data or "entity_id" in data:
        data["entity_type"] = _validate_entity(
            db,
            data.get("entity_type", current.entity_type),
            data.get("entity_id", current.entity_id),
        )
    _validate_review_status(data.get("review_status"))
    return _update(db, KnowledgeReview, item_id, data, commit=commit)


def delete_knowledge_review(db, item_id, *, commit=True):
    return _delete(db, KnowledgeReview, item_id, commit=commit)


def create_knowledge_revision(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> KnowledgeRevision:
    data = dict(values)
    data["entity_type"] = _validate_entity(
        db,
        data["entity_type"],
        data["entity_id"],
    )
    if data["version_number"] < 1:
        raise ResourceValidationError("version_number must be at least 1")
    if not isinstance(data["snapshot_json"], (dict, list)):
        raise ResourceValidationError(
            "snapshot_json must be a JSON object or array"
        )
    revision = KnowledgeRevision(**data)
    db.add(revision)
    _save(
        db,
        message="KnowledgeRevision already exists for this entity version",
        commit=commit,
    )
    return revision


def get_knowledge_revision(db, item_id):
    return _get(db, KnowledgeRevision, item_id)


def update_knowledge_revision(db, item_id, values, *, commit=True):
    data = dict(values)
    current = get_knowledge_revision(db, item_id)
    if "entity_type" in data or "entity_id" in data:
        data["entity_type"] = _validate_entity(
            db,
            data.get("entity_type", current.entity_type),
            data.get("entity_id", current.entity_id),
        )
    if (
        "snapshot_json" in data
        and not isinstance(data["snapshot_json"], (dict, list))
    ):
        raise ResourceValidationError(
            "snapshot_json must be a JSON object or array"
        )
    if data.get("version_number") is not None and data["version_number"] < 1:
        raise ResourceValidationError("version_number must be at least 1")
    return _update(db, KnowledgeRevision, item_id, data, commit=commit)


def delete_knowledge_revision(db, item_id, *, commit=True):
    return _delete(db, KnowledgeRevision, item_id, commit=commit)


def create_claim_conflict(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> ClaimConflict:
    data = dict(values)
    claim_a_id = data["claim_a_id"]
    claim_b_id = data["claim_b_id"]
    if claim_a_id == claim_b_id:
        raise ResourceValidationError("A claim cannot conflict with itself")
    if db.get(Claim, claim_a_id) is None:
        raise ResourceNotFoundError("Claim", claim_a_id)
    if db.get(Claim, claim_b_id) is None:
        raise ResourceNotFoundError("Claim", claim_b_id)
    data["claim_a_id"], data["claim_b_id"] = sorted(
        (claim_a_id, claim_b_id)
    )
    existing = db.scalar(
        select(ClaimConflict.id).where(
            ClaimConflict.claim_a_id == data["claim_a_id"],
            ClaimConflict.claim_b_id == data["claim_b_id"],
        )
    )
    if existing is not None:
        raise ResourceConflictError("Claim conflict pair already exists")
    conflict = ClaimConflict(**data)
    db.add(conflict)
    _save(
        db,
        message="Claim conflict pair already exists",
        commit=commit,
    )
    return conflict


def get_claim_conflict(db, item_id):
    return _get(db, ClaimConflict, item_id)


def update_claim_conflict(db, item_id, values, *, commit=True):
    current = get_claim_conflict(db, item_id)
    data = dict(values)
    claim_a_id = data.get("claim_a_id", current.claim_a_id)
    claim_b_id = data.get("claim_b_id", current.claim_b_id)
    if claim_a_id == claim_b_id:
        raise ResourceValidationError("A claim cannot conflict with itself")
    if "claim_a_id" in data or "claim_b_id" in data:
        if db.get(Claim, claim_a_id) is None:
            raise ResourceNotFoundError("Claim", claim_a_id)
        if db.get(Claim, claim_b_id) is None:
            raise ResourceNotFoundError("Claim", claim_b_id)
        data["claim_a_id"], data["claim_b_id"] = sorted(
            (claim_a_id, claim_b_id)
        )
    return _update(db, ClaimConflict, item_id, data, commit=commit)


def delete_claim_conflict(db, item_id, *, commit=True):
    return _delete(db, ClaimConflict, item_id, commit=commit)


def _validate_scores(data: Mapping[str, Any]) -> None:
    for field in SCORE_FIELDS:
        value = data.get(field)
        if value is not None and not 0.0 <= value <= 1.0:
            raise ResourceValidationError(
                f"{field} must be between 0.0 and 1.0"
            )


def create_source_assessment(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> SourceAssessment:
    data = dict(values)
    if db.get(Source, data["source_id"]) is None:
        raise ResourceNotFoundError("Source", data["source_id"])
    _validate_scores(data)
    assessment = SourceAssessment(**data)
    db.add(assessment)
    _save(
        db,
        message="SourceAssessment could not be created",
        commit=commit,
    )
    return assessment


def get_source_assessment(db, item_id):
    return _get(db, SourceAssessment, item_id)


def update_source_assessment(db, item_id, values, *, commit=True):
    data = dict(values)
    if (
        "source_id" in data
        and db.get(Source, data["source_id"]) is None
    ):
        raise ResourceNotFoundError("Source", data["source_id"])
    _validate_scores(data)
    return _update(db, SourceAssessment, item_id, data, commit=commit)


def delete_source_assessment(db, item_id, *, commit=True):
    return _delete(db, SourceAssessment, item_id, commit=commit)
